import logging
import boto3
import time

region = "us-west-2"
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
