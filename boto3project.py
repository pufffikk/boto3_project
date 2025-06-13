import logging
import boto3
import time

region = "us-west-2"
ec2 = boto3.client("ec2", region_name=region)


vpc_id = ec2.create_vpc(CidrBlock="10.0.0.0/23")["Vpc"]["VpcId"]
ec2.create_tags(Resources=[vpc_id], Tags=[{"Key": "Name", "Value": "Script-Vpc"}])
ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={"Value": True})

logging.info(f"VPC with id {vpc_id} was created")