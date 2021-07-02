# Update packages
sudo apt update

# Installing pip for python 3
sudo apt install python3-pip

# Installing aws cli
sudo pip3 install --upgrade awscli

# Installing aws sam 
sudo pip3 install aws-sam-cli

#intalling python modules
sudo pip3 install jump-consistent-hash==3.1.1

# Configure AWS setup
sudo aws configure

# Clone git repo
# sudo python3 /src/load_balancer.py
git clone https://github.com/ehudb9/Users_Caching_in_the_cloud.git

# Run Python3 
sudo python3 main.py
