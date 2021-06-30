from flask import Flask, redirect, url_for, request
app = Flask(__name__)
import webbrowser
new = 2 # open in a new tab, if possible



html = f"""
<html>
   <body>
      <form action = "http://localhost:5000/login" method = "post">
         <p>Enter Name:</p>
         <p><input type = "text" name = "nm" /></p>
         <p><input type = "submit" value = "submit" /></p>
      </form>   
   </body>
</html>
"""

# GET|PUT|healthcheck



@app.route('/success/<name>')
def success(name):
   return 'welcome %s' % name

@app.route('/login',methods = ['POST', 'GET'])
def login():
   if request.method == 'POST':
      user = request.form['nm']
      return redirect(url_for('success',name = user))
   else:
      user = request.args.get('nm')
      return redirect(url_for('success',name = user))

def main():
    file = open("sample.html", "w")
    file.write(html)
    file.close()
    webbrowser.open("sample.html", new=new)
    app.run(debug=True)

if __name__ == '__main__':
    main()

