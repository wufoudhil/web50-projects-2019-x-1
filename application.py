import os
import requests
from datetime import datetime


from flask import Flask, session, render_template, url_for, redirect, request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

log = False
visitor = ''
msg = ''
bid = 0
postrvu2 = False


# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    global log
    if 'username' in session:
        sessionuser = session.get("username")
        return render_template('index.html', user=sessionuser)
    elif log:
        log = False
        return render_template('index.html', user=visitor)
    return render_template('login.html')

@app.route("/signup", methods=["GET", "POST"])
def signup():
    global msg
    if request.method == "POST":
        usrnm = request.form.get("username")
        psswrd = request.form.get("password")
        ispsswrd = request.form.get("ispassword")
        accept = request.form.get("accept")
        try:
            if usrnm == '' or psswrd == '' or ispsswrd == '' or accept is None:
                msg = "Please fill in all the inputs"
                no = True
                return render_template('sign_up.html', errp=msg, no=no)
            elif psswrd != ispsswrd:
                msg = "password is not identical"
                return render_template('sign_up.html', errp=msg)
            elif db.execute("SELECT usrnm FROM users WHERE usrnm = :usrnm ", {"usrnm": usrnm}).rowcount != 0:
                if db.execute("SELECT usrnm FROM users WHERE usrnm = :usrnm ", {"usrnm": usrnm}).fetchone()[0] == usrnm:
                    msg = "Sorry the user-name already existe"
                return render_template('sign_up.html', errp=msg)
        finally:
            db.execute("INSERT INTO users (usrnm, psswd) VALUES (:usrnm, :psswrd) ", {"usrnm": usrnm, "psswrd": psswrd})
            db.commit()
            #return redirect("/")
    return render_template('sign_up.html')


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        if session.get("username"):
            logedas = session.get("username")
        else:
            logedas = visitor
        srch = request.form.get("srch")
        itmsrch = '%'+srch+'%'
        if srch == '':
            no = True
            msg = "Please type something before submitting ..."
            return render_template("index.html", errp=msg, no=no, user=logedas)
        elif db.execute("SELECT * FROM books WHERE isbn LIKE :srch or title LIKE :srch or author LIKE :srch", {"srch": itmsrch}).rowcount == 0:
            empty = True
            msg = "Sorrey we can't find what you are loocking for!"
            return render_template('index.html', empty=empty, errp=msg, user=logedas)
        else:
            books = db.execute("SELECT * FROM books WHERE isbn LIKE :itmsrch or title LIKE :itmsrch or author LIKE :itmsrch", {"itmsrch": itmsrch}).fetchall()
            return render_template("index.html", books=books, user=logedas)
    return render_template("index.html")

@app.route("/api/<isbn>")
def api(isbn):
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if book is None:
        no = True
        return render_template("404.html", msg="No such book.", no=no)
    else:
        # retrive review if existes
        rvdti = db.execute("SELECT COUNT(reviews.id), AVG(reviews.rating) FROM reviews WHERE reviews.book_id IN (SELECT books.id FROM books WHERE isbn = :isbn)", {"isbn": isbn}).fetchall()
        book = db.execute("SELECT * FROM books WHERE books.isbn = :isbn", {"isbn": isbn}).fetchall()
        return render_template("api.html", book=book, rvdti=rvdti)

@app.route("/book/<int:book_id>")
def book(book_id):
    global bid, postrvu2
    bid = book_id
    if session.get("username"):
        logedas = session.get("username")
    else:
        logedas = visitor
    # Make sure flight exists.
    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    if book is None:
        no = True
        return render_template("book.html", msg="No such book.", no=no, user=logedas)

    # Get the selected book details.
    bdetl = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchall()
    bisbn = db.execute("SELECT isbn FROM books WHERE id = :id", {"id": book_id}).fetchone()
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "gDxKNb55jRSM2GKfXODnaQ", "isbns": bisbn})
    avgrt = res.json()['books'][0]['average_rating']
    wrt = res.json()['books'][0]['work_ratings_count']

    rvn = db.execute("SELECT count(*) FROM reviews where book_id = :book_id;", {"book_id": book_id}).fetchone()[0]
    rvws = db.execute("select users.usrnm, reviews.review, reviews.rating, reviews.rvdate from users INNER JOIN reviews on reviews.user_id = users.id and reviews.book_id = :rvsbid;", {"rvsbid": book_id}).fetchall()
    if postrvu2:
        postrvu2 = False
        p2 = True
        msg = "Sorry you can't rate the same book twice!"
        return render_template("book.html", bkd=bdetl, rvn=rvn, rvws=rvws, user=logedas, msg=msg, p2=p2, avgrt=avgrt, wrt=wrt)
    else:
        return render_template("book.html", bkd=bdetl, rvn=rvn, rvws=rvws, user=logedas, avgrt=avgrt, wrt=wrt)

@app.route("/rate book", methods=["GET", "POST"])
def rate_book():
    if session.get("username"):
        logedas = session.get("username")
    else:
        logedas = visitor

    bkid = bid
    if request.method == "POST":
        txtrv = request.form.get("nwrvu")
        now = datetime.now()
        if request.form.get("stars") == None:
            ratrv = 0
        else:
            ratrv = request.form.get("stars")
        usrid = db.execute("SELECT users.id FROM public.users WHERE usrnm = :usrnm", {"usrnm": logedas}).fetchone()[0]

        if db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id", {"user_id": usrid, "book_id": bkid}).rowcount == 0:
            db.execute("INSERT INTO reviews (user_id, book_id, review, rating, rvdate) VALUES (:user_id, :book_id, :txrvu, :ratrv, :now)", {"user_id": usrid, "book_id": bkid, "txrvu": txtrv, "ratrv": ratrv, "now": now})
            db.commit()
            return redirect("/book/"+str(bkid))
        else:
            global postrvu2
            postrvu2 = True
            return redirect("/book/"+str(bkid))
            #return render_template("book.html", bkd=bdetl, rvws=rvws, user=logedas, msg=msg)

@app.route("/logout")
def logout():
    session.pop('username', None)
    return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    global log, visitor
    if request.method == "POST":
        usrnm = request.form.get("username")
        psswrd = request.form.get("password")
        rmbrme = request.form.get("rmmbrme")
        if usrnm == '' or psswrd == '':
            msg = "Please fill all the inputs"
            no = True
            return render_template('login.html', no=no, errp=msg)
        elif db.execute("SELECT * FROM users WHERE usrnm = :usrnm AND psswd = :psswrd ", {"usrnm": usrnm, "psswrd": psswrd}).rowcount == 0:
            msg = "Wrong User-name /or Password"
            return render_template('login.html', errp=msg)
        elif rmbrme:
            session["username"] = usrnm
            return redirect("/")
        elif rmbrme is None:
            visitor = usrnm
            session.pop('logged_in', None)
            log = True
            return redirect("/")

if __name__ == '__main__':
    app.secret_key = os.urandom(12)
    app.run()
