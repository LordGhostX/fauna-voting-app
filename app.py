import pytz
import hashlib
from functools import wraps
from datetime import datetime
from flask import *
from flask_bootstrap import Bootstrap
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient

app = Flask(__name__)
Bootstrap(app)
app.config["SECRET_KEY"] = "APP_SECRET_KEY"
client = FaunaClient(secret="your-secret-here")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


@app.route("/")
def index():
    return redirect(url_for("register"))


@app.route("/")
@app.route("/register/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")

        try:
            user = client.query(
                q.get(q.match(q.index("users_index"), username)))
            flash("The account you are trying to create already exists!", "danger")
        except:
            user = client.query(q.create(q.collection("users"), {
                "data": {
                    "username": username,
                    "password": hashlib.sha512(password.encode()).hexdigest(),
                    "date": datetime.now(pytz.UTC)
                }
            }))
            flash(
                "You have successfully created your account, you can now create online elections!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")

        try:
            user = client.query(
                q.get(q.match(q.index("users_index"), username)))
            if hashlib.sha512(password.encode()).hexdigest() == user["data"]["password"]:
                session["user"] = {
                    "id": user["ref"].id(),
                    "username": user["data"]["username"]
                }
                return redirect(url_for("dashboard"))
            else:
                raise Exception()
        except:
            flash(
                "You have supplied invalid login credentials, please try again!", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/dashboard/", methods=["GET"])
@login_required
def dashboard():
    elections = client.query(q.paginate(
        q.match(q.index("election_index"), session["user"]["id"])))

    elections_ref = []
    for i in elections["data"]:
        elections_ref.append(q.get(q.ref(q.collection("elections"), i.id())))

    return render_template("view-elections.html", elections=client.query(elections_ref))


@app.route("/dashboard/create-election/", methods=["GET", "POST"])
@login_required
def create_election():
    if request.method == "POST":
        title = request.form.get("title").strip()
        voting_options = request.form.get("voting-options").strip()

        options = {}
        for i in voting_options.split("\n"):
            options[i.strip()] = 0

        election = client.query(q.create(q.collection("elections"), {
            "data": {
                "creator": session["user"]["id"],
                "title": title,
                "voting_options": options,
                "date": datetime.now(pytz.UTC)
            }
        }))
        return redirect(url_for("vote", election_id=election["ref"].id()))

    return render_template("create-election.html")


@app.route("/election/<int:election_id>/", methods=["GET", "POST"])
def vote(election_id):
    try:
        election = client.query(
            q.get(q.ref(q.collection("elections"), election_id)))
    except:
        abort(404)

    if request.method == "POST":
        vote = request.form.get("vote").strip()
        election["data"]["voting_options"][vote] += 1
        client.query(q.update(q.ref(q.collection("elections"), election_id), {
                     "data": {"voting_options": election["data"]["voting_options"]}}))
        flash("Your vote was successfully recorded!", "success")
        return redirect(url_for("vote", election_id=election_id))

    return render_template("vote.html", election=election["data"])


if __name__ == "__main__":
    app.run(debug=True)
