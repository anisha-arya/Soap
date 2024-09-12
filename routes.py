# Import Flask and Flask properties, sqlite3, secrets
from flask import Flask, render_template, request, redirect, \
    url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets

app = Flask(__name__)


# Generates a 24-hex secret key
app.secret_key = secrets.token_hex(24)


def execute_query(sql, params=(), fetchone=False,
                  fetchall=False, commit=False):
    """
    Executes a query on the SQLite database.

    :param sql: The SQL query to execute.
    :param params: The parameters to pass to the query.
    :param fetchone: Whether to fetch one result.
    :param fetchall: Whether to fetch all results.
    :param commit: Whether to commit the transaction
    (use for INSERT, UPDATE, DELETE).
    :return: Result of the query if fetchone or fetchall is True,
    otherwise None.
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


# Context processor to inject the user's first name into all templates
@app.context_processor
def inject_user_firstname():
    user_firstname = None
    userid = session.get("userid")
    if userid:
        sql = "SELECT fname FROM User WHERE userid = ?"
        user = execute_query(sql, (userid,), True, False, False)
        if user:
            user_firstname = user[0]
    return dict(user_firstname=user_firstname)


# Home page route
@app.route("/")
def home():
    return render_template("home.html")


# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        sql = "SELECT * FROM User WHERE email = ?"
        user = execute_query(sql, (email,), True, False, False)

        if len(email) < 10 or len(email) > 50 or\
                len(password) < 5 or len(password) > 50:
            flash('Something went wrong, please try again soon', 'error')
            return redirect(url_for('login'))

        if user and check_password_hash(user[11], password):
            session["userid"] = user[0]
            return redirect(url_for("home"))
        else:
            flash("Incorrect email or password")

    return render_template("login.html")


# Sign up route
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        fname = request.form.get("fname", "").strip()
        lname = request.form.get("lname", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm-password", "").strip()

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", 'error')
            return redirect(url_for('signup'))

        if len(fname) > 50 or len(lname) > 50:
            flash('Name must be between 1 and 50 characters.', 'error')
            return redirect(url_for('signup'))

        if len(password) < 5 or len(password) > 100 or\
                len(email) < 5 or len(email) > 100:
            flash('Password and email must be between 5 and 100 characters.',
                  'error')
            return redirect(url_for('signup'))

        sql = "SELECT * FROM User WHERE email = ?"
        existing_user = execute_query(sql, (email,), True, False, False)

        if existing_user:
            flash("Email unavailable.\
                    Please choose another email or login.", 'error')
            return redirect(url_for('signup'))

        sql = "INSERT INTO User (fname, lname, email, password)\
                VALUES (?, ?, ?, ?)"
        execute_query(sql,
                      (fname, lname, email, generate_password_hash(password)),
                      False, False, True)
        flash("Thanks for signing up! Please log in.")
        return redirect(url_for("login"))

    return render_template("signup.html")


# Logout route
@app.route("/logout")
def logout():
    # If user wants to logout, clear the data from their session
    session.clear()
    # Tell the user they've been logged out
    flash("You have been signed out")
    # Return home.html
    return redirect(url_for("home"))


# User info route
@app.route("/user")
def userinfo():
    # Get the userid for the user currently using the site
    userid = session.get("userid")

    if not userid:
        flash("Please login to access your information")
        return render_template("login.html")

    # SQL query that gathers all the user's data
    sql = "SELECT * FROM User WHERE userid = ?"
    user = execute_query(sql, (userid,), True, False, False)

    if not user:
        # If there isn't a user, tell user
        return render_template('404.html'), 404

    # Return user.html, pass on the user's info to template
    return render_template("user.html", user=user)


# Contact route
@app.route("/customer_service", methods=["GET", "POST"])
def customer_service():
    if request.method == "POST":
        # Get form data
        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")

        # Insert the form data into the CustomerServiceRequest table
        sql = """
        INSERT INTO CustomerServiceRequest
        (name, email, subject, message)
        VALUES (?, ?, ?, ?)
        """
        execute_query(sql, (name, email, subject, message), False, False, True)

        flash("Your request has been submitted successfully.", "success")
        return redirect(url_for("customer_service"))

    # If the request method is GET, render the customer service form
    return render_template("contact.html")


# View current cart route
@app.route("/view_current_cart")
def view_current_cart():
    # Gather the userid for the user currently using the site
    userid = session.get("userid")

    if not userid:
        # If there isn't a user logged in, tell user to login
        flash("Please log in to view your cart")
        # Return login.html
        return redirect(url_for("login"))

    # SQL query checks if there is a current cart open
    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cartid = execute_query(sql, (userid,), True, False, False)

    if cartid:
        cartid = cartid[0]
    else:
        # SQL query that creates an open cart if there isn't one
        sql = """INSERT INTO Cart (userid, order_date, status)
                VALUES (?, datetime('now'), 'open')"""
        execute_query(sql, (userid,), False, False, True)
        sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
        cartid = execute_query(sql, (userid,), True, False, False)
        cartid = cartid[0]

    # SQL query that gathers all the items from the cart
    sql = """
        SELECT Soap.soapid AS soapid,
               Soap.name AS soap_name,
               Soap.price AS unit_price,
               CartItem.quantity AS soap_quantity
        FROM CartItem
        JOIN Soap ON Soap.soapid = CartItem.soapid
        WHERE CartItem.cartid = ?
        """
    cart_items = execute_query(sql, (cartid,), False, True, False)

    # Calculating the total price for all the items in the cart
    total_price = sum(
        item[2] * item[3]  # item[2] is unit_price, item[3] is soap_quantity
        for item in cart_items
    )
    # Formatting the price to 2dp
    total_price = "{:.2f}".format(total_price)

    # Format each item with its total price
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

    # Return cart.html
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
        flash("Please log in to add items to your cart")
        return redirect(url_for("login"))

    soapid = request.form.get("soapid")
    redirect_url = request.form.get("redirect_url")

    if not soapid:
        flash("No item specified to add to cart")
        return redirect(redirect_url or url_for('search'))

    try:
        # Get the open cart for the user
        sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
        cart = execute_query(sql, (userid,), True, False, False)

        if not cart:
            # No open cart exists, create a new one
            sql = """INSERT INTO Cart (userid, order_date, status)
                     VALUES (?, datetime('now'), 'open')"""
            execute_query(sql, (userid,), False, False, True)
            # Fetch the newly created cartid
            sql = """SELECT cartid FROM Cart
            WHERE userid = ? AND status = 'open'"""
            cart = execute_query(sql, (userid,), True, False, False)

        cartid = cart[0]

        # Check if the item already exists in the cart
        sql = "SELECT quantity FROM CartItem WHERE cartid = ? AND soapid = ?"
        existing_item = execute_query(sql, (cartid, soapid),
                                      True, False, False)

        # Fetch the soap name
        sql = "SELECT name FROM Soap WHERE soapid = ?"
        soap_name_result = execute_query(sql, (soapid,), True, False, False)

        if soap_name_result:
            soap_name = soap_name_result[0]
        else:
            soap_name = "Unknown item"

        if existing_item:
            # Item exists, update the quantity
            new_quantity = int(existing_item[0]) + 1
            sql = """UPDATE CartItem SET quantity = ?
                     WHERE cartid = ? AND soapid = ?"""
            execute_query(sql, (new_quantity, cartid, soapid),
                          False, False, True)
        else:
            # Item does not exist, insert a new record
            sql = """INSERT INTO CartItem (cartid, soapid, quantity)
                     VALUES (?, ?, 1)"""
            execute_query(sql, (cartid, soapid), False, False, True)

        flash(f'{soap_name} added to cart', 'success')

    except Exception as e:
        # Log the error and provide feedback
        app.logger.error(f"Error adding to cart: {e}")
        flash("An error occurred while adding the item to the cart", 'error')

    return redirect(redirect_url or url_for('search'))


# Complete order route
@app.route("/complete_order/<int:cartid>")
def complete_order(cartid):
    # Get the user's id
    userid = session.get("userid")

    if not userid:
        # If there isn't a user logged in, prompt login
        flash("Please log in to complete your order.")
        return redirect(url_for("login"))

    # SQL query that checks if the cart exists and is open
    sql = """SELECT * FROM Cart WHERE cartid = ?
    AND userid = ? AND status = 'open'"""
    cart = execute_query(sql, (cartid, userid), True, False, False)

    if not cart:
        # If the cart doesn't exist, show error page
        return render_template('404.html'), 404

    # SQL query to check if there are any items in the cart
    sql = "SELECT COUNT(*) FROM CartItem WHERE cartid = ?"
    item_count = execute_query(sql, (cartid,), True, False, False)[0]

    if item_count == 0:
        # If there are no items in the cart, inform the user
        flash("Your cart is empty. \
              You cannot complete an order without items.")
        return redirect(url_for("view_current_cart"))

    # SQL query sets the status of current cart to completed
    sql = "UPDATE Cart SET status = 'completed' WHERE cartid = ?"
    execute_query(sql, (cartid,), False, False, True)

    # Tell user order is successfully marked complete, return cart.html
    flash("Order completed!")
    return redirect(url_for("view_current_cart"))


# View previous order route
@app.route("/view_previous_order/<int:cartid>")
def view_previous_order(cartid):
    userid = session.get("userid")

    if not userid:
        flash("Please log in to view your previous order")
        return redirect(url_for("login"))

    # Check if the cart belongs to the user and is completed
    sql = "SELECT status FROM Cart WHERE cartid = ? AND userid = ?"
    result = execute_query(sql, (cartid, userid), True, False, False)

    if not result or result[0] != 'completed':
        return render_template('404.html'), 404

    # SQL query that gathers all the items from the cart
    sql = """
        SELECT Soap.soapid AS soapid,
               Soap.name AS soap_name,
               Soap.price AS unit_price,
               CartItem.quantity AS soap_quantity
        FROM CartItem
        JOIN Soap ON Soap.soapid = CartItem.soapid
        WHERE CartItem.cartid = ?
        """
    cart_items = execute_query(sql, (cartid,), False, True, False)
    # Calculating the total price for all the items in the cart
    total_price = sum(
        item[2] * item[3]  # item[2] is unit_price, item[3] is soap_quantity
        for item in cart_items
    )
    # Format total price to 2 dp
    total_price = "{:.2f}".format(total_price)

    # Format each item with its total price
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
    cart_quantities = {}

    userid = session.get('userid')

    if userid:
        # Query to get cart quantities for the logged-in user
        sql = """SELECT soapid, quantity
                 FROM CartItem
                 WHERE cartid IN (
                     SELECT cartid
                     FROM Cart
                     WHERE userid = ? AND status = 'open'
                 )"""
        items = execute_query(sql, (userid,), False, True, False)
        cart_quantities = {item[0]: item[1] for item in items}

    # Return view_previous_order.html
    return render_template(
        "view_previous_order.html",
        cart_items=formatted_cart_items,
        total_price=total_price,
        cartid=cartid,
        cart_quantities=cart_quantities
    )


@app.route("/previous_carts")
def previous_carts():
    userid = session.get("userid")

    if not userid:
        flash("Please log in to view your previous carts")
        return redirect(url_for("login"))

    sql = "SELECT * FROM Cart WHERE userid = ? AND status = 'completed'"
    completed_carts = execute_query(sql, (userid,), False, True, False)

    return render_template("previous_carts.html",
                           completed_carts=completed_carts)


# Search route
@app.route("/search")
def search():
    # Get the search term, filter, and sort parameters from the URL
    search_term = request.args.get("search_term", "").strip()
    filter_option = request.args.get("filter", "").strip()
    sort_option = request.args.get("sort", "").strip()

    # Start constructing the SQL query
    sql = "SELECT * FROM Soap WHERE name LIKE ? OR description LIKE ?"
    params = [f"%{search_term}%", f"%{search_term}%"]

    # Apply filter if one is selected
    if filter_option:
        if filter_option == "bar":
            sql += " AND type = ?"
            params.append("Bar")
        elif filter_option == "liquid":
            sql += " AND type = ?"
            params.append("Liquid")

    # Apply sorting based on the selected sort option
    if sort_option:
        if sort_option == "relevance":
            sql += " ORDER BY soapid ASC"
        elif sort_option == "ascending":
            sql += " ORDER BY price ASC"
        elif sort_option == "descending":
            sql += " ORDER BY price DESC"
        elif sort_option == "alpha":
            sql += " ORDER BY name ASC"
    else:
        # Default sorting if no specific sort is selected
        sql += " ORDER BY soapid ASC"

    # Execute the query with the constructed SQL and parameters
    results = execute_query(sql, params, False, True, False)
    # Prepare cart quantities
    cart_quantities = {}
    userid = session.get('userid')
    if userid:
        # Query to get cart quantities for the logged-in user
        sql = """SELECT soapid, quantity
                 FROM CartItem
                 WHERE cartid IN (
                     SELECT cartid
                     FROM Cart
                     WHERE userid = ? AND status = 'open'
                 )"""
        items = execute_query(sql, (userid,), False, True, False)
        cart_quantities = {item[0]: item[1] for item in items}

    # Render the template with results and cart quantities
    return render_template("search.html",
                           results=results,
                           search_term=search_term,
                           filter_option=filter_option,
                           sort_option=sort_option,
                           cart_quantities=cart_quantities)


# Decreasing quantity route
@app.route("/decrease_quantity/<int:soapid>", methods=["POST"])
def decrease_quantity(soapid):
    userid = session.get("userid")

    if not userid:
        flash("Please log in to update your cart")
        return redirect(url_for("login"))

    # Get or create an open cart
    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cart = execute_query(sql, (userid,), True, False, False)

    if not cart:
        sql = """INSERT INTO Cart (userid, order_date, status)
                VALUES (?, datetime('now'), 'open')"""
        execute_query(sql, (userid,), False, False, True)
        sql = "SELECT cartid FROM Cart WHERE userid = ?\
                            AND status = 'open'"
        cart = execute_query(sql, (userid,), True, False, False)

    cartid = cart[0]
    # Get the cart item
    sql = "SELECT quantity FROM CartItem WHERE cartid = ? AND soapid = ?"
    cart_item = execute_query(sql, (cartid, soapid), True, False, False)

    if not cart_item:
        flash("Item not found")
        return redirect(url_for("view_current_cart"))

    new_quantity = cart_item[0] - 1
    if new_quantity > 0:
        sql = """UPDATE CartItem SET quantity = ?
                 WHERE cartid = ? AND soapid = ?"""
        execute_query(sql, (new_quantity, cartid, soapid), False, False, True)
    else:
        sql = "DELETE FROM CartItem WHERE cartid = ? AND soapid = ?"
        execute_query(sql, (cartid, soapid), False, False, True)

    flash("Cart updated")

    # Get the redirect URL from the form
    redirect_url = request.form.get("redirect_url")
    return redirect(redirect_url)


@app.route('/update_info/<field>', methods=['GET', 'POST'])
def update_info(field):
    userid = session.get('userid')

    if not userid:
        flash("Please log in to manage your account.", "warning")
        return redirect(url_for('login'))

    # Define valid fields
    valid_fields = {
        'fname': 'First name',
        'lname': 'Last name',
        'email': 'Email',
        'password': 'Password',
        'address': 'Address',
    }

    # Check if the field is valid
    if field not in valid_fields:
        flash("Invalid field specified.", "error")
        return redirect(url_for('userinfo', userid=userid))

    if request.method == 'POST':
        # Special handling for updating the address
        if field == 'address':
            housenum = request.form.get("housenum")
            street = request.form.get("street")
            suburb = request.form.get("suburb")
            town = request.form.get("town")
            region = request.form.get("region")
            country = request.form.get("country")
            postcode = request.form.get("postcode")

            # Input validation
            if len(housenum) < 1 or len(housenum) > 10 or \
                len(street) < 5 or len(street) > 50 or \
                len(suburb) < 5 or len(suburb) > 50 or \
                len(town) < 5 or len(town) > 50 or \
                len(region) < 5 or len(region) > 50 or \
                len(country) < 3 or len(country) > 50 or \
                    len(postcode) < 4 or len(postcode) > 10:
                flash('Invalid address details.', 'error')
                return render_template('update_info.html', field=field,
                                       userid=userid,
                                       valid_fields=valid_fields)

            sql = """
                UPDATE User
                SET housenum = ?, street = ?, suburb = ?, town = ?, region = ?,
                           country = ?, postcode = ?
                WHERE userid = ?
            """,
            execute_query(sql,
                          (housenum, street, suburb,
                           town, region, country, postcode, userid),
                          False, False, True)

            flash("Address updated successfully.", "success")
            return redirect(url_for('userinfo', userid=userid))

        # Generic field updates (fname, lname, email, password)
        new_value = request.form.get(field)
        confirm_password = request.form.get('confirm-password')

        if new_value:
            # Special handling for password
            if field == 'password':
                if len(new_value) < 5 or len(new_value) > 50:
                    flash("Your new password must be between 5-50 characters.")
                    return render_template('update_info.html', field=field,
                                           userid=userid,
                                           valid_fields=valid_fields)
                if new_value != confirm_password:
                    flash("Passwords do not match. Please try again.", 'error')
                    return render_template('update_info.html', field=field,
                                           userid=userid,
                                           valid_fields=valid_fields)
                new_value = generate_password_hash(new_value)

            # Special handling for email
            elif field == 'email':
                sql = "SELECT * FROM User WHERE email = ?"
                used_email = execute_query(sql, (new_value,),
                                           True, False, False)
                if not used_email:
                    if len(new_value) < 5 or len(new_value) > 50:
                        flash("Your email must be between 5-50 characters")
                        return render_template('update_info.html', field=field,
                                               userid=userid,
                                               valid_fields=valid_fields)
                else:
                    flash("This email is already in use, please try again.")
                    return render_template('update_info.html', field=field,
                                           userid=userid,
                                           valid_fields=valid_fields)

            # Validation for first name and last name
            elif field == 'fname' or field == 'lname':
                if len(new_value) > 50:
                    flash("Input must be between 1-50 characters.")
                    return render_template('update_info.html', field=field,
                                           userid=userid,
                                           valid_fields=valid_fields)
            # Update the specific field in the database
            execute_query(sql, (new_value, userid), False, False, True)
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
        # Deletes the user from the User table
        sql = "DELETE FROM User WHERE userid = ?"
        execute_query(sql, (userid,), False, False, True)
        # Clear the session after account deletion
        session.clear()
        flash("Your account has been successfully deleted.", "success")
        return redirect(url_for('home'))

    # If GET request, render the confirmation page
    return render_template('delete_account.html', userid=userid)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/faqs")
def faqs():
    return render_template("faqs.html")


@app.errorhandler(404)
def page_not_found(e):
    # Render the custom 404 template
    return render_template('404.html'), 404


if __name__ == "__main__":
    app.run(debug=True)
