# Users_Caching_in_the_cloud
    By Ehud Barda and Tal Danai

## PROGRAM FLOW:
1.	AWS configs
2.	Elb starter :: create security and target groups
3.	Init N instances with instance_manager: N constant – can be changed by the User.
4.	Init HTTP server foreach Instance
5.	The server handle GET and PUT requests od data with caching distribute.
6.	Every request will handled by cache_manger and instance_manager.

## STEPS TO RUN THE CODE:
1. Assumed you have connected your cmd to `AWS-CLI`, and typed your `AWS-security-credentials`.
* Make sure you have the following policies attached to your CMD:  
* AmazonEC2FullAccess 
* IAMFullAccess
* AmazonAPIGatewayInvokeFullAccess
* AmazonAPIGatewayAdministrator
* AdministratorAccess-AWSElasticBeanstalk

2. Clone this repo
 
3. Run the file from cmd\terminal `load_ balancer.py`
 
4. Enter ```int``` number of instances wanted in ELB.

5. Wait until the instances will be connected. (Approx. 2 minutes)
All the stages will be printed in your terminal.
and finally , you will  see your instances as "healthy".

6. Usage :\
POST request:\
`<'ELB public DNS name'>/put?str_key=<your_key_value>&data=<your_data>&expiration_date=<your_date in the format dd-mm-yyyy>`\
expiration_date It is not mandatory.
If you do not send expiration_date, it will be set for 90 days <br><br>
GET request:\
`<'ELB public DNS name'>/get?str_key=<your_key_value>`

7. In order to add instance\s restart `load_balancer.py` and give the new number of wanted instances:
* if you have 3 instance and you want to add 1 you need to write 4 <br>
8. In order to remove instance\s restart `load_balancer.py` and give the new number of wanted instances:
* if you have 3 instance and you want to remove 1 you need to write 2











