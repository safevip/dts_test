# coding=utf-8
import os
import uuid
from random import choice
import logging
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
import bleach
from markdown import markdown
from flask import current_app, url_for, request

from flask_login import UserMixin, AnonymousUserMixin, current_user
from . import db, login_manager, mongodb
from .email import send_email

import bson.binary
from cStringIO import StringIO


dts_log = logging.getLogger('dts')

class Permission:
    FOLLOW = 0x01
    COMMENT = 0x02
    WRITE_ARTICLES = 0x04
    MODERATE_COMMENTS = 0x08
    ADMINISTER = 0x80


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)

    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.FOLLOW |
                     Permission.COMMENT |
                     Permission.WRITE_ARTICLES, True),
            'Moderator': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.MODERATE_COMMENTS, False),
            'Administrator': (0xff, False)
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class SoftWareInfo(db.Model):
    __tablename__ = 'softwareinfo'
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('versioninfo.id'))
    software_name = db.Column(db.String(64))
    software_descrit = db.Column(db.Text)
    software_status = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow)

    def set_status(self,status):
        dts_log.debug(str(self.id) + str(status))
        if status == '1':
            self.software_status = False
            db.session.add(self)
            return '0'
        else:
            self.software_status = True
            db.session.add(self)
            return '1'

class FeatureInfo(db.Model):
    __tablename__ = 'featureinfo'
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('versioninfo.id'))
    feature_name = db.Column(db.String(64))
    feature_descrit = db.Column(db.Text)
    feature_status = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow)

    def set_status(self,status):
        dts_log.debug(str(self.id) + str(status))
        if status == '1':
            self.feature_status = False
            db.session.add(self)
            return '0'
        else:
            self.feature_status = True
            db.session.add(self)
            return '1'

class VersionInfo(db.Model):
    __tablename__ = 'versioninfo'
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.Integer, db.ForeignKey('productinfo.id'), index=True)
    # version_id = db.Column(db.Integer, unique=True)
    version_name = db.Column(db.String(64))
    version_status = db.Column(db.Boolean, default=False)
    version_descrit = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow)

    software_fk = db.relationship('SoftWareInfo',
                           foreign_keys=[SoftWareInfo.version_id],
                           backref='software', lazy='dynamic')
    feature_fk = db.relationship('FeatureInfo',
                           foreign_keys=[FeatureInfo.version_id],
                           backref='feature', lazy='dynamic')

    @classmethod
    def get_by_product(cls, product_name):
        dts_log.debug('Get all product: %s' %product_name)
        return cls.query.join(
                    ProductInfo, ProductInfo.id == VersionInfo.product).filter(
                    ProductInfo.product_name == product_name,
                    VersionInfo.version_status==False).all()

    @classmethod
    def get_all_version(cls):
        return cls.query.filter_by(version_status=False).all()

    def set_status(self,status):
        dts_log.debug(str(self.id) + str(status))
        if status == '1':
            self.version_status = False
            db.session.add(self)
            return '0'
        else:
            self.version_status = True
            db.session.add(self)
            return '1'

    # 返回版本的名称和子版本以及特性列表
    def software_to_json(self):
        s = SoftWareInfo.query.filter_by(version_id=self.id,software_status=False).all()
        f = FeatureInfo.query.filter_by(version_id=self.id,feature_status=False).all()
        s_list = [s1.software_name for s1 in s]
        f_list = [f1.feature_name for f1 in f]
        json_post = {
            'software': self.version_name,
            'version': s_list,
            'features': f_list,
            }
        return json_post

    # 返回版本的信息
    def version_to_turple(self):
        return (self.version_name, self.version_name)

    # 返回软件版本的信息
    def software_to_turple(self):
        s = SoftWareInfo.query.filter_by(version_id=self.id).all()
        dd = []
        for soft in s:
            dd.append((soft.software_name, soft.software_name))
        return dd

    # 返回软件特性的信息
    def features_to_turple(self):
        f = FeatureInfo.query.filter_by(version_id=self.id).all()
        dd = []
        for features in f:
            dd.append((features.feature_name, features.feature_name))
        return dd


class ProductInfo(db.Model):
    __tablename__ = 'productinfo'
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(64), unique=True)
    product_descrit = db.Column(db.Text)
    # 产品状态信息，默认是false，代表没有禁止使用
    product_status = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    version_fk = db.relationship('VersionInfo',
                           foreign_keys=[VersionInfo.product],
                           backref='version', lazy='dynamic')

    @classmethod
    def get_all_product(cls):
        #查询所有状态为激活的产品
        return cls.query.filter_by(product_status=False).all()

    def set_status(self,status):
        dts_log.debug(str(self.id) + str(status))
        if status == '1':
            self.product_status = False
            db.session.add(self)
            return '0'
        else:
            self.product_status = True
            db.session.add(self)
            return '1'

    def product_name_json(self):
        json_post = {
            'name': self.product_name,
            }
        return json_post

    def product_name_turple(self):

        return (self.product_name, self.product_name)


class Process(db.Model):
    __tablename__ = 'process'
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    bugs_id = db.Column(db.String(64), db.ForeignKey('bugs.bug_id'))
    old_status = db.Column(db.Integer, db.ForeignKey('bugstatus.bug_status'))
    new_status = db.Column(db.Integer, db.ForeignKey('bugstatus.bug_status'))
    opinion = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    @staticmethod
    def process_delete(bug_id):
        try:
            Process.query.filter_by(bug_id=bug_id).delete()
        except:
            db.session.rollback()

    @staticmethod
    def after_insert(mapper, connection, target):
        user = User.query.filter_by(id=target.author_id).first()
        if str(target.old_status) == str(target.new_status):
            dts_log.debug("Status not change, No Need send email notify ")
            return None
        if user:
            token = user.generate_confirmation_token()
            send_email(user.email, u'请处理此问题单: ' + str(target.bugs_id),
                       'main/email/bug_process',
                       user=user, bug_id=target.bugs_id, target=target, token=token)
            dts_log.debug("Send mail to %s" % user.email)

db.event.listen(Process, 'after_insert', Process.after_insert)

class Bugs(db.Model):
    __tablename__ = 'bugs'
    id = db.Column(db.Integer, primary_key=True)
    bug_id = db.Column(db.String(64), unique=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    product_name = db.Column(db.String(64))
    product_version = db.Column(db.String(64))
    software_version = db.Column(db.String(64))
    version_features = db.Column(db.String(64))
    bug_level = db.Column(db.String(64))
    # 问题单知情人
    bug_insiders  = db.Column(db.String(64))
    bug_show_times = db.Column(db.String(64))
    bug_title = db.Column(db.String(64))
    bug_descrit = db.Column(db.Text)
    bug_descrit_html = db.Column(db.Text)
    bug_owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    bug_status = db.Column(db.Integer, db.ForeignKey('bugstatus.bug_status'))
    bug_photos = db.Column(db.Text)
    bug_attachments = db.Column(db.Boolean, default=False)
    resolve_version = db.Column(db.String(64))
    regression_test_version = db.Column(db.String(64))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    bug_last_update = db.Column(db.DateTime(), default=datetime.utcnow)
    bug_forbidden_status = db.Column(db.Boolean, nullable=False, default=False)
    process = db.relationship('Process',
                              foreign_keys=[Process.bugs_id],
                              backref='bugs', lazy='dynamic',
                              cascade='all, delete-orphan')

    def __repr__(self):
        return '<Bugs %r>' % self.bug_id

    #TODO 优化bugs查询，增加classmethod方法，查询方便
    @classmethod
    def get_by_bug_id(cls, bug_id):
        """非管理员禁止查看和编辑禁用的问题单"""
        if current_user.can(Permission.ADMINISTER):
            return cls.query.filter_by(bug_id=bug_id).first_or_404()
        else:
            return cls.query.filter_by(bug_forbidden_status=False).filter_by(bug_id=bug_id).first_or_404()

    @classmethod
    def bugs_filter(cls, query='list', view_args=None, request_args=None):
        dts_log.debug(view_args)
        dts_log.debug(request_args)
        product  = view_args.get('product', None)
        version  = view_args.get('version')
        software = view_args.get('software')
        features = view_args.get('features')

        date     = request_args.get('date')
        serious  = request_args.get('serious')
        status   = request_args.get('status')
        author   = request_args.get('author')
        page     = request_args.get('page',1, type=int)
        dts_log.debug(date)
        dts_log.debug(page)
        # 默认查询 默认query值为list，全部查询
        bugs_list = cls.query.filter_by(bug_forbidden_status=False)
        if current_user.can(Permission.ADMINISTER):
            # 管理员可以查询所有的问题单
            bugs_list = cls.query

        # 查询待处理的问题单列表
        if query == 'process':
            # 不用的条件的查询结果 使用union，添加组合时，使用逗号分割，不要使用and
            a = bugs_list.filter(Bugs.bug_owner == current_user ,
                          Bugs.bug_status < Bug_Now_Status.CLOSED).filter(
                          Bugs.bug_status > Bug_Now_Status.CREATED)
            b = bugs_list.filter(Bugs.author == current_user ,
                          Bugs.bug_status == Bug_Now_Status.CREATED)
            bugs_list = a.union(b)

        # 查询创建的问题单列表
        if query == 'created':
            bugs_list = bugs_list.filter_by(author=current_user)

        # 查询处理过的问题单列表
        if query == 'processed':
            # 查询的思路是表连接,要去重复值
            bugs_list = Bugs.query.filter_by(bug_forbidden_status=False).join(
                        Process,
                        Process.bugs_id == Bugs.bug_id).distinct().filter(
                        Process.operator == current_user)

        if product:
            bugs_list = bugs_list.filter(cls.product_name == product)

        if version:
            bugs_list = bugs_list.filter(cls.product_version == version)

        if software:
            bugs_list = bugs_list.filter(cls.software_version == software)

        if date:
            bugs_list = bugs_list.filter(db.func.date(Bugs.timestamp)== date)

        if features:
            bugs_list = bugs_list.filter(cls.version_features == features)

        if serious:
            bugs_list = bugs_list.filter(cls.bug_level == serious)

        if status:
            st = BugStatus.query.filter_by(bug_status_descrit=status).first()
            bugs_list = bugs_list.filter_by(now_status = st)

        if author:
            au = User.query.filter_by(username=author).first()
            bugs_list = bugs_list.filter_by(author = au)

        pagination = bugs_list.order_by(cls.timestamp.desc()).paginate(page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'], error_out=False)

        return pagination


    def set_running_manage(self, status):
        """设置问题单的运行状态，传过来的状态为当前状态，收到请求后反转状态，并返回设置后的状态"""
        if status == '1':
            self.bug_forbidden_status = False
            dts_log.debug(self.bug_id + str(status))
            db.session.add(self)
            return '0'
        else:
            self.bug_forbidden_status = True
            dts_log.debug(self.bug_id + str(status))
            db.session.add(self)
            return '1'

    def bug_delete(self):
        """删除bug"""

        dts_log.debug(u'删除问题单: ' + self.bug_id)
        #attach = Attachment.get_all_attach_by_bug_id(self.bug_id)
        #map(db.session.delete, attach)
        Attachment.attach_delete(self.bug_id)
        p = self.process.filter_by(bugs_id=self.bug_id).all()
        dts_log.debug(u'删除处理意见: ' + str(len(p)))
        map(db.session.delete, p)
        db.session.delete(self)
        db.session.commit()
        return '0'

    def to_json(self):
        """把bug的信息转换为json格式"""
        json_post = {
            'url': url_for('main.bug_process', id=self.bug_id, _external=True),
            'id': self.bug_id,
            'author': self.author.username,
            'product_name': self.product_name,
            'product_version': self.product_version,
            'software_version': self.software_version,
            'bug_level': self.bug_level,
            'bug_insiders': self.bug_insiders,
            'bug_show_times': self.bug_show_times,
            'bug_title': self.bug_title,
            'bug_owner': self.bug_owner.username,
            'bug_status': self.now_status.bug_status_descrit,
            'timestamp': self.timestamp
            }
        return json_post

    def ping(self):
        """更新最后访问时间"""
        self.bug_last_update = datetime.utcnow()
        db.session.add(self)

    def status_equal(self, status):
        """判断问题单状态是否与当前状态相等"""
        return self.bug_status is not None and self.bug_status == status

    @staticmethod
    def on_changed_bug_descrit(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        target.bug_descrit_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

db.event.listen(Bugs.bug_descrit, 'set', Bugs.on_changed_bug_descrit)

class Bug_Now_Status:
    CREATED = 1
    TESTLEADER_AUDIT = 2
    DEVELOPMENT = 3
    TESTLEADER_REGESSION = 4
    REGRESSION_TESTING = 5
    CLOSED = 6

class BugStatus(db.Model):
    __tablename__ = 'bugstatus'
    id = db.Column(db.Integer, primary_key=True)
    bug_status = db.Column(db.Integer, index=True, unique=True)
    bug_status_descrit = db.Column(db.String(64), unique=True)

    old_status = db.relationship('Process', foreign_keys=[Process.old_status],
                                 backref='old', lazy='dynamic')
    new_status = db.relationship('Process', foreign_keys=[Process.new_status],
                                 backref='new', lazy='dynamic')
    bug_now_status = db.relationship('Bugs', foreign_keys=[Bugs.bug_status],
                                     backref='now_status', lazy='dynamic')

    @staticmethod
    def insert_bug_status():
        status = [(1,u"新建"),(2,u"测试经理审核"),(3,u"开发人员定位"),(4,u"测试经理组织回归测试"),(5,u"回归测试"),(6,u"问题关闭")]
        for r in status:
            s = BugStatus()
            s.bug_status = r[0]
            s.bug_status_descrit = r[1]
            db.session.add(s)
        db.session.commit()

from string import digits, ascii_uppercase, ascii_lowercase
RANDOM_SEQ = ascii_uppercase + ascii_lowercase + digits

class Attachment(db.Model):
    __tablename__ = 'attachment'
    id = db.Column(db.Integer, primary_key = True)
    bug_id = db.Column(db.String(64), nullable=False)
    filename = db.Column(db.String(5000), nullable=False)
    filehash = db.Column(db.String(128), nullable=False)
    uploadTime = db.Column(db.DateTime(), default=datetime.utcnow)
    mimetype = db.Column(db.String(256), nullable=False)
    symlink = db.Column(db.String(64), nullable=False, unique = True)
    size = db.Column(db.Integer, nullable=False)
    confirm = db.Column(db.Boolean, default=False)

    def __init__(self, bug_id="", filename="", mimetype = "application/octet-stream", size=0, filehash=None, symlink=None):
        self.bug_id = bug_id
        self.mimetype = mimetype
        self.size = int(size)
        self.filehash = filehash if filehash else self._hash_filename(filename)
        self.filename = filename if filename else self.filehash
        self.symlink = symlink if symlink else self._gen_symlink()

    @staticmethod
    def _hash_filename(filename):
        _, _, suffix = filename.rpartition('.')
        return "%s.%s" % (uuid.uuid4().hex, suffix)

    @staticmethod
    def _gen_symlink():
        return "".join(choice(RANDOM_SEQ) for x in range(6))

    @classmethod
    def get_by_filehash(cls, filehash):
        return cls.query.filter_by(filehash=filehash).first()

    @classmethod
    def get_by_symlink(cls, symlink):
        return cls.query.filter_by(symlink=symlink).first()

    @classmethod
    def create_by_uploadFile(cls, bug_id, uploadedFile):
        rst = cls(bug_id, uploadedFile.filename, uploadedFile.mimetype, 0)

        if current_app.config['MONGO_DB_USE']:
            content = StringIO(uploadedFile.read())

            c = dict(bug_id=bug_id,
                    filename=rst.filename,
                    filehash=rst.filehash,
                    symlink=rst.symlink,
                    content=bson.binary.Binary(content.getvalue()),
                    mimetype=rst.mimetype
                    )
            mongodb.files.save(c)
        else:
            uploadedFile.save(rst.save_path)
            filestat = os.stat(rst.save_path)
            rst.size = filestat.st_size
        db.session.add(rst)
        db.session.commit()
        return rst

    @classmethod
    def get_all_attach_by_bug_id(cls, bug_id):
        rst = Attachment.query.filter_by(bug_id=bug_id).all()
        return rst

    @property
    def save_path(self):
        return os.path.join(current_app.config["UPLOAD_FOLDER"], self.filehash)

    @property
    def path(self):
        return os.path.join(current_app.config["UPLOAD_FOLDER"], self.filehash)

    @property
    def url_p(self):
        return "http://{host}/p/{filehash}".format(
            host=request.host, filehash=self.filehash)

    @property
    def url_s(self):
        return "http://{host}/s/{symlink}".format(
            host=request.host, symlink=self.symlink)

    @staticmethod
    def attach_delete(bug_id):
        pasteFile = Attachment.query.filter_by(bug_id=bug_id).all()

        for p in pasteFile:
            p.file_delete(p.symlink)


    def file_delete(self, symlink):
        pasteFile = self.get_by_symlink(symlink)

        if current_app.config['MONGO_DB_USE']:
            mongodb.files.remove({'symlink': symlink})
            db.session.delete(pasteFile)
            db.session.commit()
            return True
        else:
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], pasteFile.filehash)
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                db.session.delete(pasteFile)
                db.session.commit()
                dts_log.debug(''.join(['删除附件 ', pasteFile.filename]))
                return True
            except:
                dts_log.error(filepath)
                dts_log.error(''.join(['删除附件失败 ',pasteFile.filename]))
                return False


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    forbidden_status = db.Column(db.Boolean, default=False, nullable=False)
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    bugs = db.relationship('Bugs',
                           foreign_keys=[Bugs.author_id],
                           backref='author', lazy='dynamic')

    bugs_owner = db.relationship('Bugs',
                                 foreign_keys=[Bugs.bug_owner_id],
                                 backref='bug_owner', lazy='dynamic')

    process = db.relationship('Process',
                              foreign_keys=[Process.author_id],
                              backref='author', lazy='dynamic')
    operators = db.relationship('Process',
                                foreign_keys=[Process.operator_id],
                                backref='operator', lazy='dynamic')

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['FLASKY_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
            if self.role is None:
                dts_log.debug("Query User %s " %self.username)
                self.role = Role.query.filter_by(default=True).first()

    @classmethod
    def create_admin_user(cls, username, password, email):
        admin = cls(email=email,
                    username=username,
                    password=password,
                    role=Role.query.filter_by(name='Administrator').first(),
                    confirmed=True)

        db.session.add(admin)
        db.session.commit()
        return admin

    @classmethod
    def user_autocomplete(cls, search_str):
        return cls.query.filter_by(confirmed=True,forbidden_status=False).filter(User.email.like(search_str + '%')).all()

    @classmethod
    def get_by_email(cls, email):
        dts_log.debug("Get Email : %s" %email)
        if current_user.can(Permission.ADMINISTER):
            return cls.query.filter_by(email=email).first_or_404()
        else:
            return cls.query.filter_by(forbidden_status=False, email=email).first_or_404()

    @classmethod
    def get_by_id(cls, id):
        dts_log.debug("Get id : %s" %id)
        if current_user.can(Permission.ADMINISTER):
            return cls.query.filter_by(id=id).first_or_404()
        else:
            return cls.query.filter_by(forbidden_status=False, id=id).first_or_404()


    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id})

    def generate_reset_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset': self.id})

    def reset_password(self, token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('reset') != self.id:
            return False
        self.password = new_password
        db.session.add(self)
        return True

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def can(self, permissions):
        return self.role is not None and \
            (self.role.permissions & permissions) == permissions

    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    def set_role(self, role):
        """设置用户的角色，在管理员和普通用户间切换"""
        if role == 'ADMINISTER':
            self.role = Role.query.filter_by(permissions=0xff).first()
            dts_log.debug(self.username + ' roles now is ADMINISTER')
            db.session.add(self)
            return 'default'
        else:
            self.role = Role.query.filter_by(default=True).first()
            dts_log.debug(self.username + ' roles now is default')
            db.session.add(self)
            return 'ADMINISTER'

    def set_forbidden_status(self, status):
        """设置用户的运行状态，传过来的状态为当前状态，收到请求后反转状态，并返回设置后的状态"""
        if status == '1':
            self.forbidden_status = False
            dts_log.debug(self.username + ', '+ str(status))
            db.session.add(self)
            return '0'
        else:
            self.forbidden_status = True
            dts_log.debug(self.username + ', '+ str(status))
            db.session.add(self)
            return '1'

    def __repr__(self):
        return '<User %r>' % self.username


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

'''
class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False

login_manager.anonymous_user = AnonymousUser
'''