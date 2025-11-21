/**
 * Network Infrastructure for DAW Drug Search
 * 
 * Creates VPC, subnets, NAT gateway, and security groups
 * All resources named with "DAW" prefix/suffix
 */

import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

export function createNetwork() {
  // VPC - import existing VPC to avoid creating duplicates
  const vpc = new aws.ec2.Vpc("DAW-VPC", {
    cidrBlock: "10.0.0.0/16",
    enableDnsHostnames: true,
    enableDnsSupport: true,
    tags: {
      Name: "DAW-VPC",
      Project: "DAW",
      Component: "Network"
    }
  }, {
    import: "vpc-050fab8a9258195b7"
  });

  // Internet Gateway - import existing
  const igw = new aws.ec2.InternetGateway("DAW-IGW", {
    vpcId: vpc.id,
    tags: {
      Name: "DAW-InternetGateway",
      Project: "DAW"
    }
  }, {
    import: "igw-0f73a38de0819527c"
  });

  // Public Subnets (for NAT Gateway) - import existing
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
  }, {
    import: "subnet-0146c376a15d5458d"
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
  }, {
    import: "subnet-051f192ae7f51578f"
  });

  // Private Subnets (for Lambda, RDS, Redis) - import existing
  const privateSubnet1 = new aws.ec2.Subnet("DAW-PrivateSubnet-1", {
    vpcId: vpc.id,
    cidrBlock: "10.0.11.0/24",
    availabilityZone: "us-east-1a",
    tags: {
      Name: "DAW-PrivateSubnet-1",
      Project: "DAW",
      Type: "Private"
    }
  }, {
    import: "subnet-05ea4d85ade4340db"
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
  }, {
    import: "subnet-07c025dd82ff8355e"
  });

  // Elastic IP for NAT Gateway - import existing
  const natEip = new aws.ec2.Eip("DAW-NAT-EIP", {
    domain: "vpc",
    tags: {
      Name: "DAW-NAT-EIP",
      Project: "DAW"
    }
  }, {
    import: "eipalloc-0c51e694a058b9d3c"
  });

  // NAT Gateway (for Lambda to access Bedrock) - import existing
  const natGateway = new aws.ec2.NatGateway("DAW-NAT-Gateway", {
    allocationId: natEip.id,
    subnetId: publicSubnet1.id,
    tags: {
      Name: "DAW-NAT-Gateway",
      Project: "DAW"
    }
  }, { 
    dependsOn: [igw],
    import: "nat-0d35856153ee09ed6"
  });

  // Route Tables - import existing
  const publicRouteTable = new aws.ec2.RouteTable("DAW-PublicRouteTable", {
    vpcId: vpc.id,
    tags: {
      Name: "DAW-PublicRouteTable",
      Project: "DAW"
    }
  }, {
    import: "rtb-0facca431fbb34d21"
  });

  // Public route to Internet Gateway - already exists, skip creation
  // new aws.ec2.Route("DAW-PublicRoute", {
  //   routeTableId: publicRouteTable.id,
  //   destinationCidrBlock: "0.0.0.0/0",
  //   gatewayId: igw.id
  // });

  // Associate public subnets with public route table - already associated, skip creation
  // new aws.ec2.RouteTableAssociation("DAW-PublicSubnet-1-RTA", {
  //   subnetId: publicSubnet1.id,
  //   routeTableId: publicRouteTable.id
  // }, {
  //   import: "rtbassoc-095ec4e170b7a5e15"
  // });

  // new aws.ec2.RouteTableAssociation("DAW-PublicSubnet-2-RTA", {
  //   subnetId: publicSubnet2.id,
  //   routeTableId: publicRouteTable.id
  // }, {
  //   import: "rtbassoc-05236bb2073fe4057"
  // });

  // Private Route Table - import existing
  const privateRouteTable = new aws.ec2.RouteTable("DAW-PrivateRouteTable", {
    vpcId: vpc.id,
    tags: {
      Name: "DAW-PrivateRouteTable",
      Project: "DAW"
    }
  }, {
    import: "rtb-0151ef2f438916b3c"
  });

  // Private route to NAT Gateway - already exists, skip creation
  // new aws.ec2.Route("DAW-PrivateRoute", {
  //   routeTableId: privateRouteTable.id,
  //   destinationCidrBlock: "0.0.0.0/0",
  //   natGatewayId: natGateway.id
  // });

  // Associate private subnets with private route table - already associated, skip creation
  // new aws.ec2.RouteTableAssociation("DAW-PrivateSubnet-1-RTA", {
  //   subnetId: privateSubnet1.id,
  //   routeTableId: privateRouteTable.id
  // }, {
  //   import: "rtbassoc-06df5c8ebb2859c74"
  // });

  // new aws.ec2.RouteTableAssociation("DAW-PrivateSubnet-2-RTA", {
  //   subnetId: privateSubnet2.id,
  //   routeTableId: privateRouteTable.id
  // }, {
  //   import: "rtbassoc-04883016fbdbe4ff4"
  // });

  // Security Group for Lambda functions - import existing
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
  }, {
    import: "sg-0e78f3a483550e499"
  });

  // Security Group for Redis - import existing
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
  }, {
    import: "sg-09bc62902d8a5ad29"
  });

  // Security Group for RDS - import existing
  const rdsSecurityGroup = new aws.ec2.SecurityGroup("DAW-RDS-SG", {
    vpcId: vpc.id,
    description: "Security group for DAW Aurora RDS",
    ingress: [
      {
        protocol: "tcp",
        fromPort: 3306,
        toPort: 3306,
        securityGroups: [lambdaSecurityGroup.id],
        description: "MySQL from Lambda"
      },
      {
        protocol: "tcp",
        fromPort: 3306,
        toPort: 3306,
        securityGroups: [redisSecurityGroup.id],
        description: "MySQL from Redis EC2 (for data loading)"
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
  }, {
    import: "sg-06751ecb3d755eff2"
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

