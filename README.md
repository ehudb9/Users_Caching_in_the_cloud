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

5. <font color="red"> NOTE: </font> Currently the app.py and the distribute data unfortunately don't work.
          You will have ELB with N instances connected into target group and ready to work.

