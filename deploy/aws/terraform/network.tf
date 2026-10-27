resource "aws_vpc" "portal" { cidr_block = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support = true }
resource "aws_internet_gateway" "portal" { vpc_id = aws_vpc.portal.id }
resource "aws_subnet" "app" {
  vpc_id = aws_vpc.portal.id
  cidr_block = "10.42.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
}
resource "aws_subnet" "database" {
  count = 2
  vpc_id = aws_vpc.portal.id
  cidr_block = "10.42.${10 + count.index}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.portal.id
  route { cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.portal.id }
}
resource "aws_route_table_association" "public" { subnet_id = aws_subnet.app.id
  route_table_id = aws_route_table.public.id }
resource "aws_security_group" "app" {
  name = local.name
  vpc_id = aws_vpc.portal.id
  dynamic "ingress" {
    for_each = [80, 443]
    content { from_port = ingress.value
      to_port = ingress.value
      protocol = "tcp"
      cidr_blocks = ["0.0.0.0/0"] }
  }
  egress { from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"] }
}
resource "aws_security_group" "database" {
  name = "${local.name}-db"
  vpc_id = aws_vpc.portal.id
  ingress { from_port = 5432
    to_port = 5432
    protocol = "tcp"
    security_groups = [aws_security_group.app.id] }
}
