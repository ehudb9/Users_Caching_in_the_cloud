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

2. Clone this repo
 
3. And run `load_ balancer.py`
 
4. Enter ```int``` number of instance.

5. Wait until the instances will be connected.
All the stages will be printed in your terminal.
and finally , you will  see your instances as "healthy".
<br><br>
<font color = "red">NOTE:</font>\
   Currently the app.py and the distribute data unfortunately don't work.
   You will have ELB with N instances connected into target group and ready to work ("healthy").<br>
5. Usage :\
POST request - `<'ELB public DNS name'>/put?str_key=<your_key_value>&data=<your_data>&expiration_date=<your_date in the format dd-mm-yyyy>`\
GET request - `<'ELB public DNS name'>/get?str_key=<your_key_value>`**doesn't work**
