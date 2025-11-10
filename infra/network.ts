/**
 * Network Infrastructure for DAW Drug Search
 * 
 * Creates VPC, subnets, NAT gateway, and security groups
 * All resources named with "DAW" prefix/suffix
 */

import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

export function createNetwork() {
  // VPC
  const vpc = new aws.ec2.Vpc("DAW-VPC", {
    cidrBlock: "10.0.0.0/16",
    enableDnsHostnames: true,
    enableDnsSupport: true,
    tags: {
      Name: "DAW-VPC",
      Project: "DAW",
      Component: "Network"
    }
  });

  // Internet Gateway
  const igw = new aws.ec2.InternetGateway("DAW-IGW", {
    vpcId: vpc.id,
    tags: {
      Name: "DAW-InternetGateway",
      Project: "DAW"
    }
  });

  // Public Subnets (for NAT Gateway)
  const publicSubnet1 = new aws.ec2.Subnet("DAW-PublicSubnet-1", {
    vpcId: vpc.id,
    cidrBlock: "10.0.1.0/24",
    availabilityZone: "us-east-1a",
    mapPublicIpOnLaunch: true,
    tags: {
      Name: "DAW-PublicSubnet-1",
      Project: "DAW",
      Type: "Public"
    }
  });

  const publicSubnet2 = new aws.ec2.Subnet("DAW-PublicSubnet-2", {
    vpcId: vpc.id,
    cidrBlock: "10.0.2.0/24",
    availabilityZone: "us-east-1b",
    mapPublicIpOnLaunch: true,
    tags: {
      Name: "DAW-PublicSubnet-2",
      Project: "DAW",
      Type: "Public"
    }
  });

  // Private Subnets (for Lambda, RDS, Redis)
  const privateSubnet1 = new aws.ec2.Subnet("DAW-PrivateSubnet-1", {
    vpcId: vpc.id,
    cidrBlock: "10.0.11.0/24",
    availabilityZone: "us-east-1a",
    tags: {
      Name: "DAW-PrivateSubnet-1",
      Project: "DAW",
      Type: "Private"
    }
  });

  const privateSubnet2 = new aws.ec2.Subnet("DAW-PrivateSubnet-2", {
    vpcId: vpc.id,
    cidrBlock: "10.0.12.0/24",
    availabilityZone: "us-east-1b",
    tags: {
      Name: "DAW-PrivateSubnet-2",
      Project: "DAW",
      Type: "Private"
    }
  });

  // Elastic IP for NAT Gateway
  const natEip = new aws.ec2.Eip("DAW-NAT-EIP", {
    domain: "vpc",
    tags: {
      Name: "DAW-NAT-EIP",
      Project: "DAW"
    }
  });

  // NAT Gateway (for Lambda to access Bedrock)
  const natGateway = new aws.ec2.NatGateway("DAW-NAT-Gateway", {
    allocationId: natEip.id,
    subnetId: publicSubnet1.id,
    tags: {
      Name: "DAW-NAT-Gateway",
      Project: "DAW"
    }
  }, { dependsOn: [igw] });

  // Route Tables
  const publicRouteTable = new aws.ec2.RouteTable("DAW-PublicRouteTable", {
    vpcId: vpc.id,
    tags: {
      Name: "DAW-PublicRouteTable",
      Project: "DAW"
    }
  });

  // Public route to Internet Gateway
  new aws.ec2.Route("DAW-PublicRoute", {
    routeTableId: publicRouteTable.id,
    destinationCidrBlock: "0.0.0.0/0",
    gatewayId: igw.id
  });

  // Associate public subnets with public route table
  new aws.ec2.RouteTableAssociation("DAW-PublicSubnet-1-RTA", {
    subnetId: publicSubnet1.id,
    routeTableId: publicRouteTable.id
  });

  new aws.ec2.RouteTableAssociation("DAW-PublicSubnet-2-RTA", {
    subnetId: publicSubnet2.id,
    routeTableId: publicRouteTable.id
  });

  // Private Route Table
  const privateRouteTable = new aws.ec2.RouteTable("DAW-PrivateRouteTable", {
    vpcId: vpc.id,
    tags: {
      Name: "DAW-PrivateRouteTable",
      Project: "DAW"
    }
  });

  // Private route to NAT Gateway
  new aws.ec2.Route("DAW-PrivateRoute", {
    routeTableId: privateRouteTable.id,
    destinationCidrBlock: "0.0.0.0/0",
    natGatewayId: natGateway.id
  });

  // Associate private subnets with private route table
  new aws.ec2.RouteTableAssociation("DAW-PrivateSubnet-1-RTA", {
    subnetId: privateSubnet1.id,
    routeTableId: privateRouteTable.id
  });

  new aws.ec2.RouteTableAssociation("DAW-PrivateSubnet-2-RTA", {
    subnetId: privateSubnet2.id,
    routeTableId: privateRouteTable.id
  });

  // Security Group for Lambda functions
  const lambdaSecurityGroup = new aws.ec2.SecurityGroup("DAW-Lambda-SG", {
    vpcId: vpc.id,
    description: "Security group for DAW Lambda functions",
    egress: [{
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
      description: "Allow all outbound traffic"
    }],
    tags: {
      Name: "DAW-Lambda-SecurityGroup",
      Project: "DAW"
    }
  });

  // Security Group for Redis
  const redisSecurityGroup = new aws.ec2.SecurityGroup("DAW-Redis-SG", {
    vpcId: vpc.id,
    description: "Security group for DAW Redis EC2",
    ingress: [{
      protocol: "tcp",
      fromPort: 6379,
      toPort: 6379,
      securityGroups: [lambdaSecurityGroup.id],
      description: "Redis from Lambda"
    }],
    egress: [{
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
      description: "Allow all outbound"
    }],
    tags: {
      Name: "DAW-Redis-SecurityGroup",
      Project: "DAW"
    }
  });

  // Security Group for RDS
  const rdsSecurityGroup = new aws.ec2.SecurityGroup("DAW-RDS-SG", {
    vpcId: vpc.id,
    description: "Security group for DAW Aurora RDS",
    ingress: [
      {
        protocol: "tcp",
        fromPort: 5432,
        toPort: 5432,
        securityGroups: [lambdaSecurityGroup.id],
        description: "PostgreSQL from Lambda"
      },
      {
        protocol: "tcp",
        fromPort: 5432,
        toPort: 5432,
        securityGroups: [redisSecurityGroup.id],
        description: "PostgreSQL from Redis EC2 (for data loading)"
      }
    ],
    egress: [{
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
      description: "Allow all outbound"
    }],
    tags: {
      Name: "DAW-RDS-SecurityGroup",
      Project: "DAW"
    }
  });

  return {
    vpc,
    publicSubnets: [publicSubnet1, publicSubnet2],
    privateSubnets: [privateSubnet1, privateSubnet2],
    lambdaSecurityGroup,
    rdsSecurityGroup,
    redisSecurityGroup,
    natGateway
  };
}

