from enum import unique
from flask import Flask, request, redirect, url_for, Response, flash, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from flask_login import UserMixin, LoginManager, login_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import locale
locale.setlocale(locale.LC_ALL, "tr")

# Flask ayarları yapılıyor
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-goes-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
# SQLAlchemy nesnesi oluşturuluyor
db = SQLAlchemy(app)

# Flask Login Kütüphanesinin kurulumu yapılıyor
login_manager = LoginManager()
login_manager.init_app(app)

Base = declarative_base()

# Kullanıcı Takip Tablosu
follow = db.Table('user_followers',
                  db.Column('follower_id', db.Integer,
                            db.ForeignKey('user.id')),
                  db.Column('followed_id', db.Integer,
                            db.ForeignKey('user.id'))
                  )

# Kullanıcı Beğeni Tablosu
likes = db.Table('user_likes',
                 db.Column('user_id', db.Integer,
                           db.ForeignKey('user.id')),
                 db.Column('tweet_id', db.Integer,
                           db.ForeignKey('tweet.id'))
                 )

# Kullanıcı Retweet Tablosu
retweets = db.Table('user_retweets',
                    db.Column('user_id', db.Integer,
                              db.ForeignKey('user.id')),
                    db.Column('tweet_id', db.Integer,
                              db.ForeignKey('tweet.id')),
                    db.Column('created_at', db.DateTime(timezone=True),
                              server_default=func.now())
                    )

# Tweet Hashtag Tablosu
hashtags = db.Table('tweet_hashtags',
                    db.Column('tweet_id', db.Integer,
                              db.ForeignKey('tweet.id')),
                    db.Column('hashtag_id', db.Integer,
                              db.ForeignKey('hashtag.id'))
                    )


# Kullanıcı Modeli
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    tweets = db.relationship('Tweet', order_by="Tweet.created_at")
    following = db.relationship('User', secondary=follow, primaryjoin=(
        follow.c.follower_id == id), secondaryjoin=(follow.c.followed_id == id), backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    likes = db.relationship('Tweet', secondary=likes, backref=db.backref(
        'likes', lazy='dynamic'), lazy='dynamic')
    retweets = db.relationship('Tweet', secondary=retweets, backref=db.backref(
        'retweets', lazy='dynamic'))
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=func.now())

    def __repr__(self):
        return '<User %r>' % self.username


# Tweet Modeli
class Tweet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(280), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=func.now())
    user = db.relationship('User')

# Hashtag Modeli


class Hashtag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(100), unique=True)
    tweets = db.relationship('Tweet', secondary=hashtags, backref=db.backref(
        'hashtags', lazy='dynamic'), lazy='dynamic', order_by="Tweet.created_at")


# flask_login kütüphanesine cookie ile kullanıcıları nasıl eşletireceğini öğretiyoruz
@login_manager.user_loader
def user_loader(id):
    # cookieden gelen id ile kullanıcıyı veritabanında arıyor
    user = User.query.filter_by(id=id).first()
    if user is None:
        return
    return user


# Kullanıcı ve Hashtag işlemlerini template içinde yapabilmek için gerekli kod
@app.context_processor
def inject_stage_and_region():
    return dict(User_Query=User, Hashtag_Query=Hashtag)


# Anasayfa için home.html render ediliyor ve bütün tweetler gönderiliyor
@app.route('/')
# Bu sayfayı görebilmek için kullanıcının giriş yapması gerekli
@login_required
def home():
    return render_template("home.html", Tweets=Tweet.query.all())


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Eğer isteğin methodu GET ise login.html sayfası gösteriliyor.
    if request.method == 'GET':
        return render_template("login.html")

    # Formda verilen email ile kullanıcı aranıyor bulunur ve girilen şifre doğruysa login_user fonksiyonu çağırılıyor
    user = User.query.filter_by(email=request.form.get('email')).first()
    # check_password_hash pbkdf2 algoritması için doğrulama yapıyor
    if user is not None and check_password_hash(user.password, request.form['password']):
        login_user(user)
        return redirect(url_for('home'))

    # email veya şifre yanlış ise formda gözükmesi için hata fırlatılıyor
    flash("Kulanıcı adı veya şifre yanlış")
    # login sayfasına geri yönlendiriliyor
    return redirect(url_for('login'))


# Giriş yapmamış kullanıcıları login sayfasına yönlendiren fonksiyon
@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect('/login?next=' + request.path)


@app.route('/register', methods=['GET', 'POST'])
def register():
    # Kayıt formuna yapılan istek GET methoduysa register.html sayfası gösteriliyor
    if request.method == 'GET':
        return render_template("register.html")
    # Gönderilen formdaki emailin kullanılıp kullanılmadığına bakılıyor
    if User.query.filter_by(email=request.form.get('email')).first() is None:
        # Formda girilen verilerle yeni bir kullanıcı oluşturuluyor ve şifresi hashleniyor
        user = User(name=request.form['name'],
                    username=request.form['username'],
                    email=request.form['email'],
                    password=generate_password_hash(request.form['password']))
        # Oluşturulan kullanıcı veritabanına ekleniyor
        db.session.add(user)
        db.session.commit()
        # Kullanıcı kayıt edildikten sonra giriş yaptırılıyor ve anasayfaya yönlendiriliyor
        login_user(user)
        return redirect(url_for('home'))
    else:
        # Eğer email varsa hata fırlatılıyor
        flash("Email zaten var")
    return redirect(url_for('register'))


@app.route('/follow', methods=['POST'])
@login_required
def follow():
    # Takip edilecek kişinin idsi alınıyor
    id = request.form.get("id")
    # id yoksa anasayfaya yönlendiriliyor
    if id is not None:
        # verilen id ile ilişkili kullanıcı getiriliyor
        user = User.query.get(id)
        # kullanıcı bulunamadıysa anasayfaya yönlendiriliyor
        if user is None:
            return redirect(url_for("home"))
        # kullanıcının takipçi listesine isteği gönderen kullanıcı ekleniyor
        user.followers.append(current_user)
        db.session.commit()
    return redirect(url_for("home"))


@app.route('/unfollow', methods=['POST'])
@login_required
def unfollow():
    # Takipten çıkarılacak kişinin idsi alınıyor
    id = request.form.get("id")
    # id yoksa anasayfaya yönlendiriliyor
    if id is not None:
        # verilen id ile ilişkili kullanıcı getiriliyor
        user = User.query.get(id)
        # kullanıcı bulunamadıysa anasayfaya yönlendiriliyor
        if user is None:
            return redirect(url_for("home"))
        # kullanıcının takipçi listesinden isteği gönderen kullanıcı çıkarılıyor
        user.followers.remove(current_user)
        db.session.commit()
    return redirect(url_for("home"))


@app.route('/like', methods=['POST'])
@login_required
def like():
    # Beğenilecek tweetin idsi alınıyor
    id = request.form.get("id")
    # id yoksa anasayfaya yönlendiriliyor
    if id is not None:
        # verilen id ile ilişkili tweet getiriliyor
        tweet = Tweet.query.get(id)
        # tweet bulunamadıysa anasayfaya yönlendiriliyor
        if tweet is None:
            return redirect(url_for("home"))
        # tweetin önceden beğenilip beğenilmediği kontrol ediliyor
        if tweet.likes.filter_by(id=current_user.id).count() > 0:
            return redirect(url_for("home"))
        # tweetin beğeni listesine isteği gönderen kullanıcı ekleniyor
        tweet.likes.append(current_user)
        db.session.commit()
    return redirect(url_for("home"))


@app.route('/unlike', methods=['POST'])
@login_required
def unlike():
    # Beğenisi çekilecek tweetin idsi alınıyor
    id = request.form.get("id")
    # id yoksa anasayfaya yönlendiriliyor
    if id is not None:
        # verilen id ile ilişkili tweet getiriliyor
        tweet = Tweet.query.get(id)
        # tweet bulunamadıysa anasayfaya yönlendiriliyor
        if tweet is None:
            return redirect(url_for("home"))
        # tweetin beğeni listesinden isteği gönderen kullanıcı siliniyor
        tweet.likes.remove(current_user)
        db.session.commit()
    return redirect(url_for("home"))


@app.route('/retweet', methods=['POST'])
@login_required
def retweet():
    id = request.form.get("id")
    if id is not None:
        tweet = Tweet.query.get(id)
        if tweet is None:
            return redirect(url_for("home"))
        if tweet.retweets.filter_by(id=current_user.id).count() > 0:
            return redirect(url_for("home"))
        tweet.retweets.append(current_user)
        db.session.commit()
    return redirect(url_for("home"))


@app.route('/undo_retweet', methods=['POST'])
@login_required
def unretweet():
    id = request.form.get("id")
    if id is not None:
        tweet = Tweet.query.get(id)
        if tweet is None:
            return redirect(url_for("home"))
        tweet.retweets.remove(current_user)
        db.session.commit()
    return redirect(url_for("home"))


@app.route('/user/<path>')
def profile(path):
    # kullanıcı adı ile ilişkili kullanıcı getiriliyor
    user = User.query.filter_by(username=path).first()
    if user is not None:
        # varsa profile.html sayfasına kullanıcı bilgileri ve tweetleri gönderiliyor
        return render_template("profile.html", User=user, Tweets=user.tweets+user.retweets)
    # eğer kullanıcı yoksa 404 hatası döndürülüyor
    return Response(status=404)


@app.route('/hashtag/<tag>')
def hashtag(tag):
    # tag ile ilişkili hashtag getiriliyor
    hashtag = Hashtag.query.filter_by(tag=tag).first()
    if hashtag is not None:
        # varsa hashtag.html sayfasına hashtag bilgileri gönderiliyor
        return render_template("hashtag.html", Hashtag=hashtag)
    # eğer hashtag yoksa 404 hatası döndürülüyor
    return Response(status=404)


@app.route('/<username>/<id>')
def tweet(username, id):
    # id ile ilişkilendirilmiş tweet getiriliyor
    tweet = Tweet.query.get(id)
    # tweet yoksa 404 hatası döndürülüyor
    if tweet is None:
        return Response(status=404)
    # urldeki kullanıcı adı ile tweeti atan kişi eşleşmiyorsa 404 hatası döndürülüyor
    if tweet.user.username != username:
        return Response(status=404)
    # tweet.html sayfasına tweet bilgileri gönderiliyor
    return render_template("tweet.html", Tweet=tweet)


@app.route('/hashtags')
def hashtags():
    # hashtags.html sayfasına bütün hashtagler ve bilgileri gönderiliyor
    return render_template("hashtags.html", Hashtags=Hashtag.query.all())

@app.route('/bit', methods=[ 'POST'])
@login_required
def create_bit():
    content = request.form.get("content")
    tweet = Tweet(user_id=current_user.id,
                  content=content)
    db.session.add(tweet)
    for tag in content.split(" "):
        if not tag.startswith("#"):
            continue
        t = Hashtag.query.filter_by(tag=tag[1:]).first()
        if t is not None:
            t.tweets.append(tweet)
        else:
            t = Hashtag(tag=tag[1:])
            t.tweets.append(tweet)
            db.session.add(t)
    db.session.commit()
    return redirect(url_for('home'))