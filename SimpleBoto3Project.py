import boto3

# Region Name
region_name = "us-west-2"

# Create an S3 client
s3 = boto3.client("s3")

# Set Bucket Name
bucket_name = "deham22-bucket-v4333"

# Create a new bucket with the name "deham22-bucket-v2"
s3.create_bucket(
    Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region_name}
)

# Call S3 to list current buckets
response = s3.list_buckets()

# Get a list of all bucket names from the response
buckets = [bucket["Name"] for bucket in response["Buckets"]]
print("Bucket List: %s" % buckets)
