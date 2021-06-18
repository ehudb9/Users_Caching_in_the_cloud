server1:
Type: AWS::EC2::Instance
Properties:
  InstanceType: !Ref Server1InstanceType
  KeyName: !Ref ServerKeypair
  ImageId: !Ref ServerImageId
  SecurityGroupIds:
    - !Ref ServerSG
  SubnetId: !Ref PrivateWeb1b
  Tags:
  - Key: Name
    Value: server1

server2:
Type: AWS::EC2::Instance
Properties:
  InstanceType: !Ref Server2InstanceType
  KeyName: !Ref ServerKeypair
  ImageId: !Ref ServerImageId
  SecurityGroupIds:
    - !Ref ServerSG
  SubnetId: !Ref PrivateWeb1b
  Tags:
  - Key: Name
    Value: server2
