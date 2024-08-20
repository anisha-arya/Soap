# Import Flask and Flask properties, sqlite3, secrets
from flask import Flask, render_template, request, redirect, \
    url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets

app = Flask(__name__)


# Generates a 24-hex secret key
app.secret_key = secrets.token_hex(24)


# Context processor to inject the user's first name into all templates
@app.context_processor
def inject_user_firstname():
    user_firstname = None
    userid = session.get("userid")
    if userid:
        conn = sqlite3.connect("Soap.db")
        sql = "SELECT fname FROM User WHERE userid = ?"
        user = conn.execute(sql, (userid,)).fetchone()
        if user:
            user_firstname = user[0]
        conn.close()
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
        conn = sqlite3.connect("Soap.db")
        sql = "SELECT * FROM User WHERE email = ?"
        user = conn.execute(sql, (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user[11], password):
            session["userid"] = user[0]
            return redirect(url_for("userinfo", userid=user[0]))
        else:
            flash("Incorrect email or password")

    return render_template("login.html")


# Signup route
@app.route("/signup", methods=["GET", "POST"])
def signup():
    """ If a user wants to signup, get them to submit their firstname,
    lastname, email, and password (not null values of the User table)"""
    if request.method == "POST":
        fname = request.form["fname"]
        lname = request.form["lname"]
        email = request.form["email"]
        password = request.form["password"]
        # Hash the password
        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("Soap.db")
        # SQL for checking if there's already a user with the submitted email
        sql = "SELECT * FROM User WHERE email = ?"
        existing_user = conn.execute(sql, (email,)).fetchone()

        if existing_user:
            conn.close()
            # If there is an existing user, tell the user
            flash("Email unavailable. Please choose another email or log in.")
            # Return signup.html
            return render_template("signup.html")

        if not existing_user:
            if len(fname) < 2 or len(fname) > 50 or\
                    len(lname) < 2 or len(lname) > 50:
                flash('Name must be between 2 and 50 characters', 'error')
                return redirect(url_for('signup'))

            if len(password) < 8 or len(password) > 100 or\
                    len(email) < 8 or len(email) > 100:
                flash('Password must be between 8 and 100 characters', 'error')
                return redirect(url_for('signup'))

            sql = (
                "INSERT INTO User (fname, lname, email, password) \
                    VALUES (?, ?, ?, ?)"
                    )
            conn.execute(sql, (fname, lname, email, hashed_password))
            conn.commit()
            conn.close()

            # Tell user signup is successful, and login
            flash("Thanks for signing up!")
            # Return login.html
            return redirect(url_for("login"))

    # Return signup.html
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
@app.route("/user/<int:userid>")
def userinfo(userid):
    # Get the userid for the user currently using the site
    session_userid = session.get("userid")
    if session_userid != userid:
        # If a user is trying to access another user's info by manual URL,
        return "Hacker error", 404
    conn = sqlite3.connect("Soap.db")
    # SQL query that gathers all the user's data
    sql = "SELECT * FROM User WHERE userid = ?"
    user = conn.execute(sql, (userid,)).fetchone()
    conn.close()

    if not user:
        # If there isn't a user, tell user
        return "User not found", 404

    # Return user.html, pass on the user's info to template
    return render_template("user.html", user=user)


# Updating address route
@app.route("/user/<int:userid>/update_address", methods=["POST"])
def update_address(userid):
    housenum = request.form["housenum"]
    street = request.form["street"]
    suburb = request.form["suburb"]
    town = request.form["town"]
    region = request.form["region"]
    country = request.form["country"]
    postcode = request.form["postcode"]

    conn = sqlite3.connect("Soap.db")
    sql = "UPDATE User SET housenum = ?, street = ?, suburb = ?, town = ?,\
        region = ?, country = ?, postcode = ? WHERE userid = ?"
    conn.execute(sql, (housenum, street, suburb, town, region,
                       country, postcode, userid))
    conn.commit()
    conn.close()

    flash("Address updated successfully")
    return redirect(url_for("userinfo", userid=userid))


# Current cart route
@app.route("/view_current_cart")
def view_current_cart():
    # Gather the userid for the user currently using the site
    userid = session.get("userid")

    if not userid:
        # If there isn't a user logged in, tell user to login
        flash("Please log in to view your cart")
        # Return login.html
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")
    # SQL query checks if there is a current cart open
    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cartid = conn.execute(sql, (userid,)).fetchone()

    if cartid:
        """ If there is a current cart,
        make sure only 1 instance if being referrenced """
        cartid = cartid[0]

    if not cartid:
        # SQL query that creates an open cart if there isn't one
        sql = """INSERT INTO Cart (userid, order_date, status)
                VALUES (?, datetime('now'), 'open')"""
        conn.execute(sql, (userid,))
        conn.commit()
        # SQL query that gets the cartid of the open cart of the user
        sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
        cartid = conn.execute(sql, (userid,)).fetchone()

    """ SQL query that gathers all the items from the cart,
    sums the total quantity of each item,
    and groups the items"""
    sql = """
        SELECT Soap.soapid AS soapid,
               Soap.name AS soap_name,
               Soap.price AS unit_price,
               CartItem.quantity AS soap_quantity,
               CartItem.soapid,
               SUM(CartItem.quantity) AS total_quantity
        FROM CartItem
        JOIN Soap ON Soap.soapid = CartItem.soapid
        WHERE CartItem.cartid = ?
        GROUP BY CartItem.soapid
        """
    cart_items = conn.execute(sql, (cartid,)).fetchall()
    # Calculating the total price for all the items in the cart by
    # Multiplying the item quantity by the unit price and summing all values
    total_price = sum(
        item[2] * item[3]
        for item in cart_items)
    conn.close()

    # Return cart.html, pass on cart_items, total_price, and cartid to template
    return render_template(
        "cart.html",
        cart_items=cart_items,
        total_price=total_price,
        cartid=cartid
    )


# Add to cart route
@app.route("/add_to_cart/<int:soapid>")
def add_to_cart(soapid):
    # Get the user's id
    userid = session.get("userid")

    if not userid:
        # If there isn't a user logged in, flash message prompting login
        flash("Please log in to add items to your cart")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")
    # SQL query that gets the cartid of the open cart of the user
    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cart = conn.execute(sql, (userid,)).fetchone()

    if not cart:
        # SQL query that creates an open cart if there isn't one
        sql = """INSERT INTO Cart (userid, order_date, status)
                VALUES (?, datetime('now'), 'open')"""
        conn.execute(sql, (userid,))
        conn.commit()
        # SQL query that gets the cartid of the open cart of the user
        sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
        cart = conn.execute(sql, (userid,)).fetchone()

    # SQL query that checks how many of the selected item
    # Is currently in the cart
    sql = "SELECT quantity FROM CartItem WHERE cartid = ? AND soapid = ?"
    existing_item = conn.execute(sql, (cart[0], soapid)).fetchone()

    if existing_item:
        # If there is already that item in the cart, update the quantity by +1
        new_quantity = int(existing_item[0]) + 1
        sql = """UPDATE CartItem SET quantity = ?
            WHERE cartid = ? AND soapid = ?"""
        conn.execute(sql, (new_quantity, cart[0], soapid))
    # Otherwise just add the item to cart with quantity 1
    else:
        sql = """INSERT INTO CartItem (cartid, soapid, quantity)
            VALUES (?, ?, 1)"""
        conn.execute(sql, (cart[0], soapid))
    conn.commit()
    conn.close()

    # Tell user item has been successfully added, return cart.html
    flash(f'Item {soapid} added to cart', 'success')
    return redirect(url_for('search',
                            search_term=request.args.get('search_term')))


# Complete order route
@app.route("/complete_order/<int:cartid>")
def complete_order(cartid):
    # Get the user's id
    userid = session.get("userid")

    if not userid:
        # If there isn't a user logged in, prompt login
        flash("Please log in to complete your order.")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")

    # SQL query that checks if the cart exists and is open
    sql = """SELECT * FROM Cart WHERE cartid = ?
    AND userid = ? AND status = 'open'"""
    cart = conn.execute(sql, (cartid, userid)).fetchone()

    if not cart:
        # If the cart doesn't exist, show error page
        conn.close()
        return "Cart not found", 404

    # SQL query to check if there are any items in the cart
    sql = "SELECT COUNT(*) FROM CartItem WHERE cartid = ?"
    item_count = conn.execute(sql, (cartid,)).fetchone()[0]

    if item_count == 0:
        # If there are no items in the cart, inform the user
        conn.close()
        flash("Your cart is empty. \
              You cannot complete an order without items.")
        return redirect(url_for("view_current_cart"))

    # SQL query sets the status of current cart to completed
    sql = "UPDATE Cart SET status = 'completed' WHERE cartid = ?"
    conn.execute(sql, (cartid,))
    conn.commit()
    conn.close()

    # Tell user order is successfully marked complete, return home.html
    flash("Order completed")
    return redirect(url_for("home"))


# Previous carts route
@app.route("/previous_carts")
def previous_carts():
    # Get userid
    userid = session.get("userid")

    if not userid:
        # If there isn't a user logged in, prompt login
        flash("Please log in to view your previous carts")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")
    # SQL query gathers all the information from carts that are completed
    sql = "SELECT * FROM Cart WHERE userid = ? AND status = 'completed'"
    completed_carts = conn.execute(sql, (userid,)).fetchall()
    conn.close()

    # Return previous_carts.html, pass on completed_carts to template
    return render_template("previous_carts.html",
                           completed_carts=completed_carts)


# Search route
@app.route("/search")
def search():
    # Get the search term, filter, and sort parameters from the URL
    search_term = request.args.get("search_term", "").strip()
    filter_option = request.args.get("filter", "").strip()
    sort_option = request.args.get("sort", "").strip()

    conn = sqlite3.connect("Soap.db")

    # Start constructing the SQL query
    sql = "SELECT * FROM Soap WHERE name LIKE ?"
    params = [f"%{search_term}%"]

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
    results = conn.execute(sql, params).fetchall()
    conn.close()

    # Return search.html
    return render_template("search.html",
                           results=results, search_term=search_term,
                           filter_option=filter_option,
                           sort_option=sort_option)


# Decreasing quantity route
@app.route("/decrease_quantity/<int:soapid>")
def decrease_quantity(soapid):
    # Get user id
    userid = session.get("userid")

    if not userid:
        # If there isn't a user logged in, prompt login
        flash("Please log in to update your cart")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")
    # SQL query gathers open cart of the user
    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cart = conn.execute(sql, (userid,)).fetchone()

    if cart:
        # If there's a cart, make sure 1 instance is being referrenced
        cartid = cart[0]

    if not cart:
        # SQL query that creates an open cart if there isn't one
        sql = """INSERT INTO Cart (userid, order_date, status)
                VALUES (?, datetime('now'), 'open')"""
        conn.execute(sql, (userid,))
        conn.commit()
        # SQL query that gets the cartid of the open cart of the user
        sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
        cart = conn.execute(sql, (userid,)).fetchone()

    # SQL query gathers information about a specific item in cart
    sql = "SELECT * FROM CartItem WHERE cartid = ? AND soapid = ?"
    cart_item = conn.execute(sql, (cartid, soapid)).fetchone()

    if not cart_item:
        # If there is none of that item, tell user
        flash("Item not found")
        conn.close()
        return redirect(url_for("view_current_cart"))

    # Set new quantity as -1 less than current
    new_quantity = cart_item[2] - 1

    if new_quantity > 0:
        # If the new quantity is more than 0, update the quantity
        sql = """UPDATE CartItem SET quantity = ?
        WHERE cartid = ? AND soapid = ?"""
        conn.execute(sql, (new_quantity, cartid, soapid))
    else:
        # If the new quantity is 0, delete item from cart
        sql = "DELETE FROM CartItem WHERE cartid = ? AND soapid = ?"
        conn.execute(sql, (cartid, soapid))
    conn.commit()
    conn.close()

    # Tell user cart is successfully updated, return cart.html
    flash("Cart updated")
    return redirect(url_for("view_current_cart"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/faqs")
def faqs():
    return render_template("faqs.html")


if __name__ == "__main__":
    app.run(debug=True)
