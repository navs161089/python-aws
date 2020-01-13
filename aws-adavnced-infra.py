import boto3
pyec2 = boto3.resource('ec2')
pyclec2 = boto3.client('ec2')
inst_type = 't2.micro'
img_id = 'ami-00068cd7555f543d5'

#Create Custom VPC
cust_vpc = pyec2.create_vpc(CidrBlock='10.0.0.0/16')
cust_vpc.create_tags(Tags=[{"Key":"Name","Value":"py_custvpc"}])
cust_vpc.wait_until_available()
cust_vpcid = cust_vpc.id
print("Created the VPC:")
print(cust_vpc.id)

#Create Subnet1
subnet1 = pyec2.create_subnet(VpcId=cust_vpc.id, AvailabilityZone='us-east-1b', CidrBlock='10.0.1.0/24')
#Create Subnet2
subnet2 = pyec2.create_subnet(VpcId=cust_vpc.id, AvailabilityZone='us-east-1f', CidrBlock='10.0.2.0/24')


#Modify Subnet Attribute to AutoAssign public IPv4
pyclec2.modify_subnet_attribute(SubnetId=subnet1.id, MapPublicIpOnLaunch={'Value': True})
pyclec2.modify_subnet_attribute(SubnetId=subnet2.id, MapPublicIpOnLaunch={'Value': True})

print("Created two subnets in different AV zones:")
print(subnet1.id)
print(subnet2.id)

#Create Internet GateWay and attach to the VPC
ig_boto3 = pyec2.create_internet_gateway()
cust_vpc.attach_internet_gateway(InternetGatewayId=ig_boto3.id)

print(ig_boto3.id)

#Create Routing table and a public route
rtable_boto3 = cust_vpc.create_route_table()
route_boto3 = rtable_boto3.create_route(
    DestinationCidrBlock='0.0.0.0/0',
    GatewayId=ig_boto3.id
)
print(rtable_boto3.id)

#Associate Route Table with subnet
rtable_boto3.associate_with_subnet(SubnetId=subnet1.id)
rtable_boto3.associate_with_subnet(SubnetId=subnet2.id)

#Create SecurityGroup
sg_pyboto3 = pyec2.create_security_group(GroupName='sg_pyboto3', Description='Python Boto3', VpcId=cust_vpcid)
sgpboto3_id = sg_pyboto3.id
print(sgpboto3_id)

#Add Ingress Rules
pyboto3_data = pyclec2.authorize_security_group_ingress(
        GroupId=sgpboto3_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 80,
             'ToPort': 80,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'icmp',
             'FromPort': 21,
             'ToPort': 21,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])

#Create Instance1 on first subnet
instance1 = pyec2.create_instances(
 ImageId= img_id,
 InstanceType= inst_type,
 MaxCount=1,
 MinCount=1,
 NetworkInterfaces=[{
 'SubnetId': subnet2.id,
 'DeviceIndex': 0,
 'AssociatePublicIpAddress': True,
 'Groups': [sg_pyboto3.group_id]
 }],
 KeyName='py-boto3')

inst1 = instance1[0].id
print(inst1)


#Create Instance2 on second subnets
instance2 = pyec2.create_instances(
 ImageId= img_id,
 InstanceType= inst_type,
 MaxCount=1,
 MinCount=1,
 NetworkInterfaces=[{
 'SubnetId': subnet2.id,
 'DeviceIndex': 0,
 'AssociatePublicIpAddress': True,
 'Groups': [sg_pyboto3.group_id]
 }],
 KeyName='py-boto3')

inst2 = instance2[0].id
print(inst2)


#Create Load Balancer
lb = boto3.client('elbv2')
lb_out = lb.create_load_balancer(
    Name='my-boto3-lb',
    SecurityGroups=[
        sgpboto3_id,
    ],	
    Subnets=[
        subnet1.id,
        subnet2.id,
    ],
)
print(lb_out)

#Create Target Groups
tg_out = lb.create_target_group(
    Name='my-boto3-targets',
    Port=80,
    Protocol='HTTP',
    VpcId=cust_vpcid,
)
print(tg_out)

##Find out ARNs of TragetGroup and LoadBalancer
tgrp = tg_out.get('TargetGroups')
tgrp_arn = tgrp[0].get('TargetGroupArn')
print(tgrp_arn)

lbr = lb_out.get('LoadBalancers')
lb_arn = lbr[0].get('LoadBalancerArn')
print(lb_arn)

#Register Targets
reg_target = lb.register_targets(
    TargetGroupArn=tgrp_arn,
    Targets=[
        {
            'Id': inst1,
        },
        {
            'Id': inst2,
        },
    ],
)

print(reg_target)

#Create Listener
lb_listen = lb.create_listener(
    DefaultActions=[
        {
            'TargetGroupArn': tgrp_arn,
            'Type': 'forward',
        },
    ],
    LoadBalancerArn=lb_arn,
    Port=80,
    Protocol='HTTP',
)

print(lb_listen)
