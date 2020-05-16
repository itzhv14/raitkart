import json
import os
from datetime import datetime
from functools import wraps
from flask_wtf import CsrfProtect
from MySQLdb.cursors import Cursor
from flask import Flask, render_template, flash, redirect, url_for, session, request
from flask_mail import Mail
from flask_mysqldb import MySQL
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from passlib.handlers import mysql
from werkzeug.utils import secure_filename
from wtforms import Form, StringField, PasswordField, validators, TextAreaField, SelectField


# json file contains email id and pass
with open('config.json', 'r') as c:
    params = json.load(c)["params"]

app = Flask(__name__, static_url_path='/static')
app.secret_key = "super secret key"
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'raitkart'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT='465',
    MAIL_USE_SSL=True,
    MAIL_USERNAME=params['gmail-user'],
    MAIL_PASSWORD=params['gmail-password']
)

mail = Mail(app)
# init MYSQL
mysql = MySQL(app)
csrf = CsrfProtect()


def create_app():
    app = Flask(__name__)

    app.config.from_object('config.settings')

    csrf.init_app(app)


@app.route('/')
def main():
    return render_template('dashboard.html')


# about page banana hai
@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/home')
def home():
    return render_template('home.html')


# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('login'))

    return wrap


# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))


# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    return render_template("dashboard.html")


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = Contact(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        roll_no = form.roll_no.data
        phone_no = form.phone_no.data
        email = form.email.data
        message = form.message.data
        # date = datetime.now()
        # Create Cursor
        cur: Cursor = mysql.connection.cursor()

        # Execute
        cur.execute(
            "INSERT INTO contact(name, roll_no, phone_no, email, message, date) VALUES(%s, %s, %s, %s, %s, %s)",
            (name, roll_no, phone_no, email, message, datetime.now())
        )

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()
        mail.send_message('Mail from RAITKART',
                          sender=[params['gmail-user']],
                          recipients=[email],
                          body="Thank you for contacting us"
                          )
        mail.send_message('New message from ' + name,
                          sender=email,
                          recipients=[params['gmail-user']],
                          body=f"Message: {message}\n"
                               f"Roll no: {roll_no}\n"
                               f"Phone no: {phone_no}\n"
                          )

        flash('Message Sent. Thank You for your feedback', 'success')
        return redirect(url_for("dashboard"))
    return render_template('contact.html', params=params, form=form)


# User Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    session.clear()
    form = RegisterForm(request.form)
    cur = mysql.connection.cursor()
    if request.method == 'POST' and form.validate():
        roll_no = form.roll_no.data
        result = cur.execute("SELECT * FROM users WHERE roll_no = %s", [roll_no])

        if result == 1:
            cur.close()
            flash("Already Registered, Please Login", "danger")
            return redirect('login')

        else:
            roll_no = form.roll_no.data
            name = form.name.data
            email = form.email.data
            phone_no = form.phone_no.data
            password = form.password.data

            # Create cursor
            cur = mysql.connection.cursor()

            # Execute query insert karne k liye users table me
            cur.execute("INSERT INTO users (roll_no, name, email, phone_no, password) VALUES (%s, %s, %s, %s, %s)",
                        (roll_no, name, email, phone_no, password))

            # Commit to DB
            mysql.connection.commit()
            # Close connection
            cur.close()

            # msg bhi flash honge
            flash('You are registered, Please login', 'success')
            return redirect(url_for('login'))

    return render_template('register.html', form=form)


# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST':
        # Get Form Fields
        roll_no = form.roll_no.data
        password_candidate = form.password.data

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by roll_no
        result = cur.execute("SELECT * FROM users WHERE roll_no = %s", [roll_no])

        if result == 1:
            # Get stored hash
            data = cur.fetchone()
            password = data['password']
            name = data['name']
            email = data['email']
            phone_no = data['phone_no']

            # Compare Passwords
            if password_candidate == password:
                # Passed
                session['logged_in'] = True
                session['roll_no'] = roll_no
                session['name'] = name
                session['email'] = email
                session['phone_no'] = phone_no

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                # Close connection
                cur.close()
                error = 'Invalid password'
                return render_template('login.html', form=form, error=error)

        else:
            error = 'Roll No. not found. Please register!'
            return render_template('login.html', form=form, error=error)

    return render_template('login.html', form=form)


# Add product
@app.route('/sell', methods=['GET', 'POST'])
@is_logged_in
def sell():
    form = Sell()
    if form.validate_on_submit():
        title = form.title.data
        category = form.category.data
        description = form.description.data
        price = form.price.data
        date = datetime.now()

        f = request.files['picture']
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)))
        url = f.filename
        # Create Cursor
        cur: Cursor = mysql.connection.cursor()

        # Execute
        cur.execute(
            "INSERT INTO products (title, category, description, roll_no, price, date, phone_no, photo) VALUES(%s, %s, "
            "%s, %s, %s, %s, %s, %s)",
            (title, category, description, session['roll_no'], price, date, session['phone_no'], url))

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash('Product Added', 'success')
        return redirect(url_for('products'))

    return render_template('sell.html', form=form)


@app.route('/buy')
@is_logged_in
def buy():
    # Create cursor
    cur = mysql.connection.cursor()

    # Get products
    result = cur.execute("SELECT * FROM products EXCEPT SELECT * FROM products WHERE roll_no=%s", [session['roll_no']])

    products = cur.fetchall()
    # Close connection
    cur.close()
    if result > 0:
        return render_template('buy.html', products=products)
    else:
        msg = 'No Products Found'
        return render_template('buy.html', msg=msg)


@app.route('/products')
@is_logged_in
def products():
    # Create cursor
    cur = mysql.connection.cursor()

    # Show products only from the user logged in
    result = cur.execute("SELECT * FROM products WHERE roll_no = %s", [session['roll_no']])

    products = cur.fetchall()
    cur.close()
    if result > 0:
        return render_template('products.html', products=products)
    else:
        msg = 'No Product Found'
        return render_template('products.html', msg=msg)


# Single product
@app.route('/product/<string:id>/')
def product(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Get product
    result = cur.execute("SELECT * FROM products WHERE id = %s", [id])

    product = cur.fetchone()

    return render_template('product.html', product=product)


# Edit product
@app.route('/edit_product/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_products(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Get product by id
    cur.execute("SELECT * FROM products WHERE id = %s", [id])

    product = cur.fetchone()
    cur.close()
    # Get form
    form = Sell(request.form)

    # Populate product form fields
    form.title.data = product['title']
    form.category.data = product['category']
    form.description.data = product['description']
    form.price.data = product['price']

    if request.method == 'POST' and form.validate():
        title = request.form['title']
        f = request.files['picture']
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)))
        url = f.filename

        category = request.form['category']
        description = request.form['description']
        price = request.form['price']

        # Create Cursor
        cur = mysql.connection.cursor()
        # Execute
        cur.execute("UPDATE products SET title=%s, category=%s, description=%s, price=%s, photo=%s WHERE id=%s",
                    (title, category, description, price, url, id))
        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash('Product Updated', 'success')

        return redirect(url_for('products'))

    return render_template('edit_product.html', form=form)


# Delete product
@app.route('/delete_product/<string:id>', methods=['POST'])
@is_logged_in
def delete_product(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute("DELETE FROM products WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    # Close connection
    cur.close()

    flash('Product removed', 'success')

    return redirect(url_for('products'))


@app.route("/profile", methods=['GET', 'POST'])
@is_logged_in
def profile():
    roll_no = session['roll_no']
    cur = mysql.connection.cursor()

    # Get product
    cur.execute("SELECT * FROM users WHERE roll_no = %s", [roll_no])
    user = cur.fetchone()
    cur.close()
    return render_template('profile.html', user=user)


@app.route("/edit_profile", methods=['GET', 'POST'])
@is_logged_in
def edit_profile():
    form = ProfileForm(request.form)
    form.name.data = session['name']
    form.email.data = session['email']
    form.phone_no.data = session['phone_no']

    if request.method == 'POST' and form.validate():
        name = request.form['name']
        email = request.form['email']
        phone_no = request.form['phone_no']
        roll_no = session['roll_no']

        # Create Cursor
        cur = mysql.connection.cursor()

        # Execute
        cur.execute("UPDATE users SET name=%s, email=%s, phone_no=%s WHERE roll_no = %s",
                    (name, email, phone_no, roll_no))
        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()
        session.clear()
        flash('Profile Updated. Login again!', 'success')

        return redirect(url_for('login'))

    return render_template('edit_profile.html', form=form)


@app.route("/edit_password", methods=['GET', 'POST'])
@is_logged_in
def change_pass():
    form = PassForm(request.form)
    if request.method == 'POST' and form.validate():
        password = form.password.data
        roll_no = session['roll_no']

        cur = mysql.connection.cursor()

        # Execute
        cur.execute("UPDATE users SET password=%s WHERE roll_no = %s",
                    (password, roll_no))
        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()
        session.clear()
        flash('Password Changed. Login again!', 'success')

        return redirect(url_for('login'))

    return render_template('edit_password.html', form=form)


@app.route('/chat', methods=['GET', 'POST'])
@is_logged_in
def chat():
    lis = []

    # Create cursor
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM msg WHERE sender = %s or receiver= %s",
                [session['roll_no'], session['roll_no']])
    messages = cur.fetchall()

    for i in messages:
        lis.append(i['sender'].upper())
        lis.append(i['receiver'].upper())
    lis = list(dict.fromkeys(lis))

    cur.close()

    return render_template('chat.html', messages=messages, lis=lis)


@app.route('/chat/<string:receiver>/', methods=['GET', 'POST'])
def chats(receiver):
    receiver = receiver

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM msg WHERE (receiver = %s and sender= %s) or (receiver = %s and sender= %s) ",
                [session['roll_no'], receiver, receiver, session['roll_no']])

    messages = cur.fetchall()
    cur.close()
    form = ChatForm()
    if form.validate_on_submit():
        receiver = receiver
        message = form.message.data
        sender = session['roll_no']
        date = datetime.now()

        cur: Cursor = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO msg (message, sender, receiver, date) VALUES(%s, %s, "
            "%s, %s)",
            (message, sender, receiver, date))

        # Commit to DB
        mysql.connection.commit()
        cur.close()

        render_template('chats.html', messages=messages, form=form, receiver=receiver)
        return redirect('')
    return render_template('chats.html', messages=messages, form=form, receiver=receiver)


class Contact(Form):
    roll_no: StringField = StringField('Roll No', [
        validators.Length(max=8, min=8),
        validators.DataRequired()])
    name = StringField('Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    email = StringField('Email', [validators.Length(min=6, max=50), validators.DataRequired(), ])
    phone_no = StringField('Phone No', [
        validators.Length(max=10, min=10),
        validators.DataRequired(), ])
    message = TextAreaField('Message', [
        validators.DataRequired(), ])


class RegisterForm(Form):
    roll_no: StringField = StringField('Roll No', [
        validators.Length(max=8, min=8),
        validators.DataRequired()])
    name = StringField('Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    email = StringField('Email', [validators.Length(min=6, max=50), validators.DataRequired(), ])
    phone_no = StringField('Phone No', [
        validators.Length(max=10, min=10),
        validators.DataRequired(),
    ])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


class LoginForm(Form):
    roll_no: StringField = StringField('Roll No', [
        validators.Length(max=8, min=8),
        validators.DataRequired()])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])


class NewSelectField(SelectField):
    def pre_validate(self, form):
        pass


class Sell(FlaskForm):
    title = StringField('Title', [validators.Length(min=1, max=20), validators.DataRequired()])
    description = TextAreaField('Description', [validators.DataRequired()])
    category = NewSelectField('Category', choices=[('Books', 'Books'), ('Drawing_Stuffs', 'Drawing_Stuffs'),
                                                   ('Electronic_Gadgets', 'Electronic_Gadgets'), ('Others', 'Others')])
    price = StringField('Price', [validators.DataRequired()])
    date = datetime.now()
    picture = FileField('Product Picture', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])


class ChatForm(FlaskForm):
    message = TextAreaField('Message:', [validators.DataRequired()])


class ProfileForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    email = StringField('Email', [validators.Length(min=6, max=50), validators.DataRequired(), ])
    phone_no = StringField('Phone No', [
        validators.Length(max=10, min=10),
        validators.DataRequired(),
    ])


class PassForm(Form):
    password = PasswordField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


if __name__ == '__main__':
    app.run(debug=True)