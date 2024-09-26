# Import necessary modules: Flask properties for web app,
# Sqlite3 for database interactions, and secrets for secure token generation
from flask import Flask, render_template, request, redirect, \
    url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets

app = Flask(__name__)


# Generates a 24-hex secret key to secure session data
app.secret_key = secrets.token_hex(24)


def execute_query(sql, params=(), fetchone=False,
                  fetchall=False, commit=False):
    """
    Executes a query on the SQLite database.

    Simplified explanation:
    - Executes SQL with optional parameters.
    - Optionally fetches one or all results.
    - Optionally commits transactions (e.g., INSERT, UPDATE, DELETE).
    """
    connection = sqlite3.connect("Soap.db")
    cursor = connection.cursor()
    result = None

    try:
        cursor.execute(sql, params)
        if commit:
            connection.commit()

        if fetchone:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()

    except sqlite3.Error as e:
        app.logger.error(f"Database error: {e}")
        raise

    finally:
        connection.close()

    return result


# Inject the user's first name into all templates if logged in
@app.context_processor
def inject_user_firstname():
    user_firstname = None
    userid = session.get("userid")
    if userid:
        sql = "SELECT fname FROM User WHERE userid = ?"
        user = execute_query(sql, (userid,), fetchone=True)
        if user:
            user_firstname = user[0]
    return dict(user_firstname=user_firstname)


# Home page route displaying featured items and a gallery of products
@app.route("/")
def home():
    # SQL query to fetch featured items
    featured_sql = "SELECT name, picture, description\
        FROM Soap WHERE is_featured=1"
    featured_items = execute_query(featured_sql, fetchall=True)

    # SQL query to fetch all items for the gallery
    sql = "SELECT name, picture FROM Soap"
    items = execute_query(sql, fetchall=True)

    return render_template("home.html", featured_items=featured_items,
                           items=items)


# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Query the database for the user with the provided email
        sql = "SELECT * FROM User WHERE email = ?"
        user = execute_query(sql, (email,), fetchone=True)

        # Basic form validation for email and password lengths
        if len(email) < 10 or len(email) > 50 or\
                len(password) < 5 or len(password) > 50:
            flash('Something went wrong, please try again soon', 'error')
            return redirect(url_for('login'))

        # Verify password and log in user
        if user and check_password_hash(user[11], password):
            session["userid"] = user[0]
            return redirect(url_for("home"))
        else:
            flash("Incorrect email or password", 'error')

    return render_template("login.html")


# Sign up route
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        # Gather user inputs, removing whitespace
        fname = request.form.get("fname", "").strip()
        lname = request.form.get("lname", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm-password", "").strip()

        # Ensure password confirmation matches
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", 'error')
            return redirect(url_for('signup'))

        # Validate name length and password strength
        if len(fname) > 50 or len(lname) > 50:
            flash('Name must be between 1 and 50 characters.', 'error')
            return redirect(url_for('signup'))

        if len(password) < 5 or len(password) > 100:
            flash('Password must be between 5 and 100 characters.',
                  'error')
            return redirect(url_for('signup'))

        # Check if the email is already in use
        sql = "SELECT * FROM User WHERE email = ?"
        existing_user = execute_query(sql, (email,), fetchone=True)

        if existing_user:
            flash("Email unavailable.\
                  Please choose another email or login.", 'error')
            return redirect(url_for('signup'))

        # Insert new user into the database with hashed password
        sql = "INSERT INTO User (fname, lname, email, password)\
                VALUES (?, ?, ?, ?)"
        execute_query(sql, (fname, lname, email,
                            generate_password_hash(password)),
                      commit=True)
        flash("Thanks for signing up! Please log in.", 'success')
        return redirect(url_for("login"))

    return render_template("signup.html")


# Logout route that clears session data
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out", 'success')
    return redirect(url_for("home"))


# Route for displaying user information
@app.route("/user")
def userinfo():
    userid = session.get("userid")

    if not userid:
        flash("Please login to access your information", 'message')
        return render_template("login.html")

    # SQL query to fetch the logged-in user's information
    sql = "SELECT * FROM User WHERE userid = ?"
    user = execute_query(sql, (userid,), fetchone=True)

    if not user:
        return render_template('404.html'), 404

    return render_template("user.html", user=user)


# Customer service contact form route
@app.route("/customer_service", methods=["GET", "POST"])
def customer_service():
    if request.method == "POST":
        # Collect form data
        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")

        # Insert contact form data into the database
        sql = """
        INSERT INTO CustomerServiceRequest
        (name, email, subject, message)
        VALUES (?, ?, ?, ?)
        """
        execute_query(sql, (name, email, subject, message), commit=True)

        flash("Your request has been submitted successfully.", "success")
        return redirect(url_for("customer_service"))

    return render_template("contact.html")


# View current cart route
@app.route("/view_current_cart")
def view_current_cart():
    userid = session.get("userid")

    if not userid:
        flash("Please log in to view your cart", 'message')
        return redirect(url_for("login"))

    # SQL query to check if the user has an open cart
    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cartid = execute_query(sql, (userid,), fetchone=True)

    if cartid:
        cartid = cartid[0]
    else:
        # Create a new cart if none exists
        sql = """INSERT INTO Cart (userid, order_date, status)
                VALUES (?, datetime('now'), 'open')"""
        execute_query(sql, (userid,), commit=True)
        sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
        cartid = execute_query(sql, (userid,), fetchone=True)
        cartid = cartid[0]

    # SQL query to gather items in the cart
    sql = """
        SELECT Soap.soapid AS soapid,
               Soap.name AS soap_name,
               Soap.price AS unit_price,
               CartItem.quantity AS soap_quantity
        FROM CartItem
        JOIN Soap ON Soap.soapid = CartItem.soapid
        WHERE CartItem.cartid = ?
        """
    cart_items = execute_query(sql, (cartid,), fetchall=True)

    # Calculate total price for all items in the cart
    total_price = sum(item[2] * item[3] for item in cart_items)
    total_price = "{:.2f}".format(total_price)

    # Format each cart item with total price
    formatted_cart_items = [
        {
            "soapid": item[0],
            "soap_name": item[1],
            "unit_price": "{:.2f}".format(item[2]),
            "soap_quantity": item[3],
            "total_unit_price": "{:.2f}".format(item[2] * item[3])
        }
        for item in cart_items
    ]

    return render_template(
        "cart.html",
        cart_items=formatted_cart_items,
        total_price=total_price,
        cartid=cartid
    )


# Add to cart route
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    userid = session.get("userid")
    if not userid:
        # Redirect to login if user isn't logged in
        flash("Please log in to add items to your cart", 'message')
        return redirect(url_for("login"))

    # Get soapid from form and the URL to redirect to
    soapid = request.form.get("soapid")
    redirect_url = request.form.get("redirect_url")

    if not soapid:
        # No item to add to cart, redirect to search page
        flash("No item specified to add to cart", 'error')
        return redirect(redirect_url or url_for('search'))

    try:
        # Check for an open cart for the user
        sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
        cart = execute_query(sql, (userid,), True)

        if not cart:
            # Create a new cart if no open cart exists
            sql = """INSERT INTO Cart (userid, order_date, status)
                     VALUES (?, datetime('now'), 'open')"""
            execute_query(sql, (userid,), commit=True)
            # Fetch the newly created cart's ID
            sql = "SELECT cartid FROM Cart \
                WHERE userid = ? AND status = 'open'"
            cart = execute_query(sql, (userid,), True)

        cartid = cart[0]

        # Check if the item is already in the cart
        sql = "SELECT quantity FROM CartItem WHERE cartid = ? AND soapid = ?"
        existing_item = execute_query(sql, (cartid, soapid), True)

        # Fetch the soap name to show in the flash message
        sql = "SELECT name FROM Soap WHERE soapid = ?"
        soap_name_result = execute_query(sql, (soapid,), True)
        soap_name = soap_name_result[0] if soap_name_result else "Unknown item"

        if existing_item:
            # If item exists, increase the quantity
            new_quantity = int(existing_item[0]) + 1
            sql = "UPDATE CartItem SET quantity = ? \
                WHERE cartid = ? AND soapid = ?"
            execute_query(sql, (new_quantity, cartid, soapid), commit=True)
        else:
            # If item does not exist, insert it into the cart
            sql = "INSERT INTO CartItem (cartid, soapid, quantity) \
                VALUES (?, ?, 1)"
            execute_query(sql, (cartid, soapid), commit=True)

        flash(f'{soap_name} added to cart', 'success')

    except Exception as e:
        # Log the error if an issue occurs and inform the user
        app.logger.error(f"Error adding to cart: {e}")
        flash("An error occurred while adding the item to the cart", 'error')

    # Redirect back to the page the user was on
    return redirect(redirect_url or url_for('search'))


# Complete order route
@app.route("/complete_order/<int:cartid>")
def complete_order(cartid):
    userid = session.get("userid")

    if not userid:
        # Redirect to login if user isn't logged in
        flash("Please log in to complete your order.", 'message')
        return redirect(url_for("login"))

    # Verify the cart belongs to the user and is open
    sql = """SELECT * FROM Cart WHERE cartid = ? \
        AND userid = ? AND status = 'open'"""
    cart = execute_query(sql, (cartid, userid), True)

    if not cart:
        # If the cart doesn't exist or isn't open, show error page
        return render_template('404.html'), 404

    # Check if the cart has any items
    sql = "SELECT COUNT(*) FROM CartItem WHERE cartid = ?"
    item_count = execute_query(sql, (cartid,), True)[0]

    if item_count == 0:
        # Prevent order completion if cart is empty
        flash("Your cart is empty. \
              You cannot complete an order without items.", 'error')
        return redirect(url_for("view_current_cart"))

    # Update the cart's status to 'completed'
    sql = "UPDATE Cart SET status = 'completed' WHERE cartid = ?"
    execute_query(sql, (cartid,), commit=True)

    flash("Order completed! \
          To view the contents of this order, \
          please explore your previous carts", 'success')
    return redirect(url_for("view_current_cart"))


# View previous order route
@app.route("/view_previous_order/<int:cartid>")
def view_previous_order(cartid):
    userid = session.get("userid")

    if not userid:
        flash("Please log in to view your previous order", 'message')
        return redirect(url_for("login"))

    # Check if the cart is completed and belongs to the user
    sql = "SELECT status FROM Cart WHERE cartid = ? AND userid = ?"
    result = execute_query(sql, (cartid, userid), True)

    if not result or result[0] != 'completed':
        # If cart isn't found or not completed, show error page
        return render_template('404.html'), 404

    # Fetch items from the completed cart
    sql = """
        SELECT Soap.soapid, Soap.name, Soap.price, CartItem.quantity
        FROM CartItem
        JOIN Soap ON Soap.soapid = CartItem.soapid
        WHERE CartItem.cartid = ?
        """
    cart_items = execute_query(sql, (cartid,), fetchall=True)

    # Calculate the total price
    total_price = "{:.2f}".format(sum(item[2] * item[3]
                                      for item in cart_items))

    # Format items for display
    formatted_cart_items = [
        {
            "soapid": item[0],
            "soap_name": item[1],
            "unit_price": "{:.2f}".format(item[2]),
            "soap_quantity": item[3],
            "total_unit_price": "{:.2f}".format(item[2] * item[3])
        }
        for item in cart_items
    ]

    # Return the previous order details
    return render_template("view_previous_order.html",
                           cart_items=formatted_cart_items,
                           total_price=total_price,
                           cartid=cartid)


# View previous carts route
@app.route("/previous_carts")
def previous_carts():
    userid = session.get("userid")

    if not userid:
        flash("Please log in to view your previous carts", 'message')
        return redirect(url_for("login"))

    # Fetch all completed carts for the user
    sql = "SELECT * FROM Cart WHERE userid = ? AND status = 'completed'"
    completed_carts = execute_query(sql, (userid,), fetchall=True)

    return render_template("previous_carts.html",
                           completed_carts=completed_carts)


# Search route
@app.route("/search")
def search():
    search_term = request.args.get("search_term", "").strip()
    sort_option = request.args.get("sort", "").strip()

    sql = "SELECT * FROM Soap WHERE name LIKE ? OR description LIKE ?"
    # Stores the search parameters if sort is chosen
    params = [f"%{search_term}%", f"%{search_term}%"]

    if sort_option:
        if sort_option == "ascending":
            sql += " ORDER BY price ASC"
        elif sort_option == "descending":
            sql += " ORDER BY price DESC"
        elif sort_option == "alpha":
            sql += " ORDER BY name ASC"
    else:
        sql += " ORDER BY soapid ASC"

    results = execute_query(sql, params, fetchall=True)

    cart_quantities = {}
    userid = session.get('userid')
    if userid:
        # SQL for gathering the quantity of soaps for button display
        sql = """SELECT soapid, quantity
                 FROM CartItem
                 WHERE cartid IN (
                     SELECT cartid
                     FROM Cart
                     WHERE userid = ? AND status = 'open'
                 )"""
        items = execute_query(sql, (userid,), fetchall=True)
        # Stores quantities in a dictionary for template
        cart_quantities = {item[0]: item[1] for item in items}

    return render_template("search.html", results=results,
                           search_term=search_term, sort_option=sort_option,
                           cart_quantities=cart_quantities)


# Decreasing quantity route
@app.route("/decrease_quantity/<int:soapid>", methods=["POST"])
def decrease_quantity(soapid):
    userid = session.get("userid")

    if not userid:
        flash("Please log in to update your cart", 'message')
        return redirect(url_for("login"))

    # Selects the user's open cart
    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cart = execute_query(sql, (userid,), fetchone=True)

    if not cart:
        sql = """INSERT INTO Cart (userid, order_date, status)
                VALUES (?, datetime('now'), 'open')"""
        execute_query(sql, (userid,), commit=True)
        # Fetches the id of the cart just created
        cart = execute_query(sql, (userid,), fetchone=True)

    cartid = cart[0]
    sql = "SELECT quantity FROM CartItem WHERE cartid = ? AND soapid = ?"
    cart_item = execute_query(sql, (cartid, soapid), fetchone=True)

    if not cart_item:
        flash("Item not found", 'error')
        return redirect(url_for("view_current_cart"))

    new_quantity = cart_item[0] - 1

    # Updates quantity if it's not 0, otherwise deletes item
    if new_quantity > 0:
        sql = """UPDATE CartItem SET quantity = ? \
            WHERE cartid = ? AND soapid = ?"""
        execute_query(sql, (new_quantity, cartid, soapid), commit=True)
    else:
        sql = "DELETE FROM CartItem WHERE cartid = ? AND soapid = ?"
        execute_query(sql, (cartid, soapid), commit=True)

    flash("Cart updated", 'success')
    return redirect(request.form.get("redirect_url"))


# Update info route
@app.route('/update_info/<field>', methods=['GET', 'POST'])
def update_info(field):
    userid = session.get('userid')

    if not userid:
        flash("Please log in to manage your account.", "message")
        return redirect(url_for('login'))

    # Storing update fields in a dictionary for rendering
    valid_fields = {
        'fname': 'First name',
        'lname': 'Last name',
        'email': 'Email',
        'password': 'Password',
        'address': 'Address',
    }

    if field not in valid_fields:
        flash("Invalid field specified.", "error")
        return redirect(url_for('userinfo', userid=userid))

    if request.method == 'POST':
        if field == 'address':
            housenum = request.form.get("housenum")
            street = request.form.get("street")
            suburb = request.form.get("suburb")
            town = request.form.get("town")
            region = request.form.get("region")
            country = request.form.get("country")
            postcode = request.form.get("postcode")

            # Checks that the lengths of the inputs are valid, then updates
            if any(len(val) < 3 or len(val) > 50
                   for val in [street, suburb, town, region, country]) or \
               len(housenum) < 1 or len(housenum) > 10 or \
               len(postcode) < 4 or len(postcode) > 10:
                flash('Invalid address details.', 'error')
                return render_template('update_info.html', field=field,
                                       userid=userid,
                                       valid_fields=valid_fields)

            sql = """UPDATE User SET housenum = ?, street = ?, \
                suburb = ?, town = ?, region = ?, country = ?, \
                    postcode = ? WHERE userid = ?"""
            execute_query(sql, (housenum, street, suburb, town, region,
                                country, postcode, userid), False, False, True)

            flash("Address updated successfully.", "success")
            return redirect(url_for('userinfo', userid=userid))

        new_value = request.form.get(field)
        confirm_password = request.form.get('confirm-password')

        if new_value:
            if field == 'password':
                # Check password length is valid
                if len(new_value) < 5 or len(new_value) > 50:
                    flash("Your new password must be \
                          between 5-50 characters.", 'message')
                    return render_template('update_info.html', field=field,
                                           userid=userid,
                                           valid_fields=valid_fields)
                # If the passwords don't match
                if new_value != confirm_password:
                    flash("Passwords do not match. Please try again.", 'error')
                    return render_template('update_info.html', field=field,
                                           userid=userid,
                                           valid_fields=valid_fields)
                # Hashing new password
                new_value = generate_password_hash(new_value)

            elif field == 'email':
                sql = "SELECT * FROM User WHERE email = ?"
                used_email = execute_query(sql, (new_value,), fetchone=True)

                if not used_email:
                    # If email not already in use, check email length
                    if len(new_value) < 5 or len(new_value) > 50:
                        flash("Your email must be between 5-50 characters",
                              'message')
                        return render_template('update_info.html', field=field,
                                               userid=userid,
                                               valid_fields=valid_fields)
                else:
                    flash("This email is already in use, please try again.",
                          'error')
                    return render_template('update_info.html', field=field,
                                           userid=userid,
                                           valid_fields=valid_fields)

            elif field in ['fname', 'lname'] and len(new_value) > 50:
                # Check name length is valid
                flash("Names must be between 1-50 characters.", 'message')
                return render_template('update_info.html', field=field,
                                       userid=userid,
                                       valid_fields=valid_fields)

            # Versatile query for updating different fields
            sql = f"UPDATE User SET {field} = ? WHERE userid = ?"
            execute_query(sql, (new_value, userid), commit=True)
            flash(f"{valid_fields[field]} updated successfully.", "success")
            return redirect(url_for('userinfo', userid=userid))

    return render_template('update_info.html', field=field,
                           userid=userid,
                           valid_fields=valid_fields)


# Delete account route
@app.route('/delete_account', methods=['GET', 'POST'])
def delete_account():
    userid = session.get('userid')

    if not userid:
        flash("Please log in to manage your account.", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        sql = "DELETE FROM User WHERE userid = ?"
        execute_query(sql, (userid,), commit=True)
        # Clears user session once account is deleted
        session.clear()
        flash("Your account has been successfully deleted.", "success")
        return redirect(url_for('home'))

    return render_template('delete_account.html', userid=userid)


# About page
@app.route("/about")
def about():
    return render_template("about.html")


# FAQs page
@app.route("/faqs")
def faqs():
    return render_template("faqs.html")


# Image credits page
@app.route("/credits")
def credit():
    return render_template("credit.html")


if __name__ == "__main__":
    app.run(debug=True)
