from flask import Flask, render_template, request, redirect, \
    url_for, flash, session
import sqlite3
import secrets

app = Flask(__name__)

app.secret_key = secrets.token_hex(24)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    user = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("Soap.db")
        sql = "SELECT * FROM User WHERE email = ? AND password = ?"
        user = conn.execute(sql, (email, password)).fetchone()
        conn.close()

    if user:
        session["userid"] = user[0]
        return redirect(url_for("userinfo", userid=user[0]))

    if not user:
        flash("Invalid email or password. Try again or sign up to continue")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        fname = request.form["fname"]
        lname = request.form["lname"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("Soap.db")
        sql = "SELECT * FROM User WHERE email = ?"
        existing_user = conn.execute(sql, (email,)).fetchone()

        if existing_user:
            conn.close()
            flash("Email unavailable. Please choose another email or log in.")
            return render_template("signup.html")

        sql = (
            "INSERT INTO User (fname, lname, email, password) \
                VALUES (?, ?, ?, ?)"
                )
        conn.execute(sql, (fname, lname, email, password))
        conn.commit()
        conn.close()

        flash("Thanks for signing up! Please login to continue")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out")
    return redirect(url_for("home"))


@app.route("/user/<int:userid>")
def userinfo(userid):
    conn = sqlite3.connect("Soap.db")
    sql = "SELECT * FROM User WHERE userid = ?"
    user = conn.execute(sql, (userid,)).fetchone()
    conn.close()

    if not user:
        return "User not found", 404

    return render_template("user.html", user=user)


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

    flash("Address updated successfully.")
    return redirect(url_for("userinfo", userid=userid))


@app.route("/view_current_cart")
def view_current_cart():
    userid = session.get("userid")

    if not userid:
        flash("Please log in to view your cart")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")

    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cartid = conn.execute(sql, (userid,)).fetchone()

    if cartid:
        cartid = cartid[0]

    if not cartid:
        flash("No cart found")
        conn.close()
        return redirect(url_for("home"))

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

    total_price = sum(
        item[2] * item[3]
        for item in cart_items)
    conn.close()

    return render_template(
        "cart.html",
        cart_items=cart_items,
        total_price=total_price,
        cartid=cartid
    )


@app.route("/add_to_cart/<int:soapid>")
def add_to_cart(soapid):
    userid = session.get("userid")

    if not userid:
        flash("Please log in to add items to your cart")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")

    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cart = conn.execute(sql, (userid,)).fetchone()

    if not cart:
        sql = """INSERT INTO Cart (userid, order_date, status)
                VALUES (?, datetime('now'), 'open')"""
        conn.execute(sql, (userid,))
        conn.commit()

        sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
        cart = conn.execute(sql, (userid,)).fetchone()

    sql = "SELECT quantity FROM CartItem WHERE cartid = ? AND soapid = ?"
    existing_item = conn.execute(sql, (cart[0], soapid)).fetchone()

    if existing_item:
        new_quantity = int(existing_item[0]) + 1
        sql = """UPDATE CartItem SET quantity = ?
            WHERE cartid = ? AND soapid = ?"""
        conn.execute(sql, (new_quantity, cart[0], soapid))
    else:
        sql = """INSERT INTO CartItem (cartid, soapid, quantity)
            VALUES (?, ?, 1)"""
        conn.execute(sql, (cart[0], soapid))

    conn.commit()
    conn.close()

    flash("Item added to your cart")
    return redirect(url_for("view_current_cart"))


@app.route("/complete_order/<int:cartid>")
def complete_order(cartid):
    userid = session.get("userid")

    if not userid:
        flash("Please log in to complete your order.")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")
    sql = "SELECT * FROM Cart WHERE cartid = ? \
        AND userid = ? AND status = 'open'"
    cart = conn.execute(sql, (cartid, userid)).fetchone()

    if not cart:
        return "Cart not found", 404

    sql = "UPDATE Cart SET status = 'completed' WHERE cartid = ?"
    conn.execute(sql, (cartid,))
    conn.commit()
    conn.close()

    flash("Order completed")
    return redirect(url_for("home"))


@app.route("/previous_carts")
def previous_carts():
    userid = session.get("userid")

    if not userid:
        flash("Please log in to view your previous carts")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")

    sql = "SELECT * FROM Cart WHERE userid = ? AND status = 'completed'"
    completed_carts = conn.execute(sql, (userid,)).fetchall()
    conn.close()

    return render_template("previous_carts.html",
                           completed_carts=completed_carts)


@app.route("/search", methods=["GET", "POST"])
def search():
    search_term = request.args.get("search_term", "").strip()

    conn = sqlite3.connect("Soap.db")
    sql = "SELECT * FROM Soap WHERE name LIKE ? OR description LIKE ?"
    results = conn.execute(sql, (f"%{search_term}%",
                                 f"%{search_term}%")).fetchall()
    conn.close()

    return render_template("search.html",
                           results=results, search_term=search_term)


@app.route("/decrease_quantity/<int:soapid>")
def decrease_quantity(soapid):
    userid = session.get("userid")

    if not userid:
        flash("Please log in to update your cart")
        return redirect(url_for("login"))

    conn = sqlite3.connect("Soap.db")

    sql = "SELECT cartid FROM Cart WHERE userid = ? AND status = 'open'"
    cart = conn.execute(sql, (userid,)).fetchone()

    if cart:
        cartid = cart[0]

    if not cart:
        flash("No open cart found")
        conn.close()
        return redirect(url_for("home"))

    sql = "SELECT * FROM CartItem WHERE cartid = ? AND soapid = ?"
    cart_item = conn.execute(sql, (cartid, soapid)).fetchone()

    if not cart_item:
        flash("Item not found")
        conn.close()
        return redirect(url_for("view_current_cart"))

    new_quantity = cart_item[2] - 1

    if new_quantity > 0:
        sql = """UPDATE CartItem SET quantity = ?
        WHERE cartid = ? AND soapid = ?"""
        conn.execute(sql, (new_quantity, cartid, soapid))
    else:
        sql = "DELETE FROM CartItem WHERE cartid = ? AND soapid = ?"
        conn.execute(sql, (cartid, soapid))
    conn.commit()
    conn.close()

    flash("Cart updated")
    return redirect(url_for("view_current_cart"))


if __name__ == "__main__":
    app.run(debug=True)
