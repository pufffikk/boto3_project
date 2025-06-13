import logging
import boto3
import requests
import base64

region = "us-west-2"

ssm = boto3.client("ssm", region_name=region)

response = ssm.get_parameter(
    Name="/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2"
)

AMI_ID = response["Parameter"]["Value"]

ec2 = boto3.client("ec2", region_name=region)

logging.getLogger().setLevel(logging.INFO)
vpc_id = ec2.create_vpc(CidrBlock="10.0.0.0/23")["Vpc"]["VpcId"]
ec2.create_tags(Resources=[vpc_id], Tags=[{"Key": "Name", "Value": "Script-Vpc"}])
ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={"Value": True})

logging.info(f"VPC with id {vpc_id} was created")


def create_subnet(cidr, az, name):
    subnet_id = ec2.create_subnet(VpcId=vpc_id, CidrBlock=cidr, AvailabilityZone=az)["Subnet"]["SubnetId"]
    ec2.create_tags(Resources=[subnet_id], Tags=[{"Key": "Name", "Value": name}])
    return subnet_id


pub1 = create_subnet("10.0.0.0/27", "us-west-2a", "Public Subnet 1")
pub2 = create_subnet("10.0.0.64/27", "us-west-2b", "Public Subnet 2")
priv1 = create_subnet("10.0.0.128/26", "us-west-2a", "Private Subnet 1")
priv2 = create_subnet("10.0.1.0/26", "us-west-2b", "Private Subnet 2")

for sid in [pub1, pub2]:
    ec2.modify_subnet_attribute(SubnetId=sid, MapPublicIpOnLaunch={"Value": True})

logging.info(f"Subnets with ids {pub1, pub2, priv1, priv2} were created")

igw_id = ec2.create_internet_gateway()["InternetGateway"]["InternetGatewayId"]
ec2.create_tags(Resources=[igw_id], Tags=[{"Key": "Name", "Value": "Script-IGW"}])
ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)

logging.info(f"Internet getaway with id {igw_id} was created")

rtb_id = ec2.create_route_table(VpcId=vpc_id)["RouteTable"]["RouteTableId"]
ec2.create_tags(Resources=[rtb_id], Tags=[{"Key": "Name", "Value": "Public Route Table"}])
ec2.create_route(RouteTableId=rtb_id, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw_id)

for sid in [pub1, pub2]:
    ec2.associate_route_table(RouteTableId=rtb_id, SubnetId=sid)

logging.info(f"Public Rout table with id {rtb_id} was created")

eip_alloc_id = ec2.allocate_address(Domain="vpc")["AllocationId"]
nat_gw_id = ec2.create_nat_gateway(SubnetId=pub1, AllocationId=eip_alloc_id)["NatGateway"]["NatGatewayId"]

logging.info("Waiting for NAT Gateway to become available...")
ec2.get_waiter("nat_gateway_available").wait(NatGatewayIds=[nat_gw_id])

logging.info(f"NAT Gateway with {nat_gw_id} is available")

priv_rtb_id = ec2.create_route_table(VpcId=vpc_id)["RouteTable"]["RouteTableId"]
ec2.create_route(RouteTableId=priv_rtb_id, DestinationCidrBlock="0.0.0.0/0", NatGatewayId=nat_gw_id)

for sid in [priv1, priv2]:
    ec2.associate_route_table(RouteTableId=priv_rtb_id, SubnetId=sid)

logging.info(f"Private Rout table with id {priv_rtb_id} was created")

rds = boto3.client("rds", region_name=region)

db_sg_id = ec2.create_security_group(
    GroupName="DB-SG",
    Description="Allow MySQL access from Bastion",
    VpcId=vpc_id
)["GroupId"]

logging.info(f"DB security group with id {db_sg_id} was created")

ec2.authorize_security_group_ingress(
    GroupId=db_sg_id,
    IpProtocol="tcp",
    FromPort=3306,
    ToPort=3306,
    CidrIp="10.0.0.0/16"
)

rds.create_db_subnet_group(
    DBSubnetGroupName="my-db-subnet-group",
    DBSubnetGroupDescription="RDS Subnet Group",
    SubnetIds=[pub1, pub2, priv1, priv2]
)

rds.create_db_instance(
    DBInstanceIdentifier="database-1",
    DBInstanceClass="db.t3.micro",
    Engine="mysql",
    AllocatedStorage=100,
    StorageType="gp2",
    MasterUsername="admin",
    MasterUserPassword="12345678",
    DBSubnetGroupName="my-db-subnet-group",
    VpcSecurityGroupIds=[db_sg_id],
    BackupRetentionPeriod=0,
    StorageEncrypted=False,
    EnablePerformanceInsights=False,
    AvailabilityZone="us-west-2a"
)

logging.info("RDS Instance launching...")

my_ip = requests.get("https://checkip.amazonaws.com").text.strip() + "/32"

bastion_sg_id = ec2.create_security_group(
    GroupName="Bastion-SG",
    Description="Allow SSH and HTTP from my IP",
    VpcId=vpc_id
)["GroupId"]

for port in [22, 80]:
    ec2.authorize_security_group_ingress(
        GroupId=bastion_sg_id,
        IpProtocol="tcp",
        FromPort=port,
        ToPort=port,
        CidrIp=my_ip
    )

user_data_script = '''#!/bin/bash
sudo yum update -y
sudo amazon-linux-extras enable php8.0 mariadb10.5
sudo yum clean metadata
sudo yum install -y php php-mysqlnd mariadb unzip httpd
sudo systemctl start httpd
sudo systemctl enable httpd
sudo systemctl start mariadb
sudo systemctl enable mariadb
cd /var/www/html
sudo wget https://wordpress.org/latest.zip
sudo unzip latest.zip
sudo cp -r wordpress/* .
sudo rm -rf wordpress latest.zip
sudo chown -R apache:apache /var/www/html
'''

user_data_encoded = base64.b64encode(user_data_script.encode("utf-8")).decode("utf-8")

ec2.run_instances(
    ImageId=AMI_ID,
    InstanceType="t3.micro",
    SubnetId=pub1,
    KeyName="vockey",
    SecurityGroupIds=[bastion_sg_id],
    MinCount=1,
    MaxCount=1,
    UserData=user_data_script,
    TagSpecifications=[{
        "ResourceType": "instance",
        "Tags": [{"Key": "Name", "Value": "Bastion Server"}]
    }]
)

logging.info("Bastion EC2 instance launched.")
