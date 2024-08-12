from http.client import HTTPException
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_compress import Compress
from flask import send_from_directory
from datetime import datetime
from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy import or_
from sqlalchemy import and_
import random
import string
import os
import re

# Create a Flask app
app = Flask(__name__)
Compress(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'database.db')
app.config['SECRET_KEY'] = 'secret' # Change this!
db = SQLAlchemy(app)

# Create a database model
class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    link_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(1500), nullable=True)
    link = db.Column(db.String(500), nullable=False)
    ip_address = db.Column(db.String(15), nullable=False)
    ip_addresses = db.Column(db.String, default="")
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_name = db.Column(db.String(100), nullable=False, default='anonymous')
    views = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active') # Set the default value to 'active'/ 'verified' if the leak is legit

# Create database tables if they don't exist already
with app.app_context():
    db.create_all()

# Format a number to be more readable
def format_num(num):
    if num < 1000:
        return str(num)
    elif num < 1000000:
        return f"{num / 1000:.1f}K"
    else:
        return f"{num / 1000000:.1f}M"

@app.context_processor
def utility_processor():
    def format_num(num):
        if num < 1000:
            return str(num)
        elif num < 1000000:
            return f"{num / 1000:.1f}K"
        else:
            return f"{num / 1000000:.1f}M"
    return dict(format_num=format_num)

# Home page
@app.route('/')
def home():
    # Get the 20 most recent links
    links = Link.query.order_by(Link.date_posted.desc()).limit(20).all()
    # Count the total number of links
    total_links = Link.query.count()
    formatted_total_links = format_num(total_links)
    # Calculate the total views
    total_views = sum(link.views for link in Link.query.all())
    formatted_total_views = format_num(total_views)
    # Render the home page
    return render_template('index.html', links=links, total_links=total_links, formatted_total_links=formatted_total_links, formatted_total_views=formatted_total_views)

# Magnet page
@app.route('/magnet/<link_name>')
def magnet(link_name):
    # Get the link from the database
    link = Link.query.filter_by(link_name=link_name).first_or_404()
    # Get the viewer's IP address
    ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    # Check if the IP address is already in the ip_addresses field
    ip_addresses = link.ip_addresses.split(',') if link.ip_addresses else []
    if ip_address not in ip_addresses:
        # Increment the views if the user hasn't viewed the page yet
        if not session.get(f'viewed_{link_name}'):
            link.views += 1
            # Remember that the user has viewed the page
            session[f'viewed_{link_name}'] = True
        # Add the IP address to the ip_addresses field
        ip_addresses.append(ip_address)
        link.ip_addresses = ','.join(ip_addresses)
        db.session.commit()
    # Count the total number of links
    total_links = Link.query.count()
    formatted_total_links = format_num(total_links)
    # Calculate the total views
    total_views = sum(link.views for link in Link.query.all())
    formatted_total_views = format_num(total_views)
    # Render the magnet page
    return render_template('magnet.html', link=link, formatted_total_links=formatted_total_links, formatted_total_views=formatted_total_views)

# Search page
@app.route('/search')
def search():
    # Get the query and sort order from the URL parameters
    query = request.args.get('q')
    if not re.search(r'\w', query):
        return redirect(url_for('home'))
    sort_order = request.args.get('sort', 'most_recent')
    page = request.args.get('page', 1, type=int)
    # Split the query into words and search for each word
    words = query.split()
    filters = []
    for word in words:
        filters.append(Link.title.contains(word))
        filters.append(Link.description.contains(word))
        filters.append(Link.user_name.contains(word))
    links = Link.query.filter(or_(*filters))
    # Sort the results based on the sort order
    if sort_order == 'most_recent':
        links = links.order_by(desc(Link.date_posted))
    elif sort_order == 'most_older':
        links = links.order_by(Link.date_posted)
    elif sort_order == 'most_views':
        links = links.order_by(desc(Link.views))
    elif sort_order == 'least_views':
        links = links.order_by(Link.views)
    # Paginate the results
    links = links.paginate(page=page, per_page=5)
    # Count the total number of links
    total_links = Link.query.count()
    formatted_total_links = format_num(total_links)
    # Calculate the total views
    total_views = sum(link.views for link in Link.query.all())
    formatted_total_views = format_num(total_views)
    # Render the search results page with the current search query
    return render_template('search.html', links=links, query=query, sort_order=sort_order, formatted_total_links=formatted_total_links, formatted_total_views=formatted_total_views)

# Submit page
@app.route('/submit', methods=['GET', 'POST'])
def submit():
    # Count the total number of links
    total_links = Link.query.count()
    formatted_total_links = format_num(total_links)
    # Calculate the total views
    total_views = sum(link.views for link in Link.query.all())
    formatted_total_views = format_num(total_views)
    if request.method == 'POST':
        # Get the title, description, and magnet link from the form data
        title = request.form.get('title')
        title = title.replace('<', '').replace('>', '')
        title = re.sub(' {6,}', '     ', title)
        description = request.form.get('description') or 'No description provided.'
        description = description.replace('<', '').replace('>', '')
        description = re.sub('\n{3,}', '\n\n', description)
        description = re.sub(r'(<br>\s*){2,}', '<br>', description.replace('\n', '<br>'))
        magnet_link = request.form.get('link')
        user_name = re.sub(' {6,}', '     ', request.form.get('user_name') or 'anonymous')
        user_name = user_name.replace("/", "").replace("\\", "")
        # Get the IP address of the client
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        # Generate a unique link name
        link_name = 'leak-' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
        # Check if the IP address has already posted 10 times today
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        link_count = Link.query.filter(and_(Link.ip_address == ip_address, Link.date_posted >= start_time, Link.date_posted < end_time)).count()
        if link_count >= 10:
            return render_template('submit.html', error='You have reached the limit of 10 submits per day.')
        # Check if it's a valid magnet link, if the title and description are within the character limit, and if the title and description are not empty
        if re.match(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}', magnet_link) and len(title) <= 100 and len(user_name) <= 30 and len(description) <= 1500 and title and description:
            # Add the magnet link to the database
            new_link = Link(title=title, link_name=link_name, description=description, link=magnet_link, ip_address=ip_address, user_name=user_name)
            db.session.add(new_link)
            db.session.commit()
            # Redirect to the magnet page
            # After adding the magnet link to the database
            flash('Magnet link added successfully.')
            return redirect(url_for('magnet', link_name=link_name))
        else:
            # If it's not a valid magnet link or if the title or description are too long, render the post page with an error message
            return render_template('submit.html', error='Invalid input. Make sure your magnet link is valid, your title is no more than 100 characters, your username is no more than 30 characters, and your description is no more than 1500 characters.', formatted_total_links=formatted_total_links, formatted_total_views=formatted_total_views)
    else:
        # Render the post page
        return render_template('submit.html', formatted_total_links=formatted_total_links, formatted_total_views=formatted_total_views)

# Admin
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    # Count the total number of links
    total_links = Link.query.count()
    formatted_total_links = format_num(total_links)
    # Calculate the total views
    total_views = sum(link.views for link in Link.query.all())
    formatted_total_views = format_num(total_views)
    if request.method == 'POST':
        link_name = request.form.get('link_name')
        # Find the link with the given link_name
        link = Link.query.filter_by(link_name=link_name).first()
        if link is None:
            flash('Link not found.')
            return redirect(url_for('admin'))

        # Delete the link
        db.session.delete(link)
        db.session.commit()

        flash('Link deleted successfully.')
        return redirect(url_for('admin'))

    # Render the admin page
    return render_template('admin.html', formatted_total_links=formatted_total_links, formatted_total_views=formatted_total_views)

# favicon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path,'static'), 'img/favicon.ico', mimetype='image/vnd.microsoft.icon')    

# error handlers
@app.errorhandler(Exception)
def handle_error(error):
    # Count the total number of links
    total_links = Link.query.count()
    formatted_total_links = format_num(total_links)
    # Calculate the total views
    total_views = sum(link.views for link in Link.query.all())
    formatted_total_views = format_num(total_views)
    # Get the error code and message
    code = error.code
    if isinstance(error, HTTPException):
        code = error.code
    message = str(error)
    # Render the error page
    return render_template('error.html', error=f"{message}", formatted_total_links=formatted_total_links, formatted_total_views=formatted_total_views), code

# Start the webapp in dev mode
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
