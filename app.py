from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import Error
import pandas as pd  # For reading CSV
import os  # For checking if CSV exists

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'  # !! CHANGE THIS TO A STRONG, RANDOM KEY IN PRODUCTION !!

# 🔹 Database connection helper
def get_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="deekshu15@2006",  # <<-- UPDATE THIS PASSWORD IF YOUR MYSQL ROOT PASSWORD IS DIFFERENT
            database="library"
        )
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None


def load_books_from_csv():
    csv_file = 'Departmentwise BooksData.csv'
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found. Please place it in the app directory.")
        return

    try:
        df = pd.read_csv(csv_file)

    
        df.rename(columns={'Department': 'category', 'Author': 'author', 'Title': 'title', 'Year': 'year'}, inplace=True)

        df = df.dropna(subset=['title', 'author', 'category', 'year'])

        def safe_int(x):
            try:
                return int(x)
            except:
                return None
        df['year'] = df['year'].apply(safe_int)
        df = df.dropna(subset=['year'])

        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            # Clear existing books to avoid duplicates on re-run
            cursor.execute("DELETE FROM books")
            conn.commit()
            print("Existing books cleared from database.")

            for index, row in df.iterrows():
                title = row['title']
                author = row['author']
                category = row['category']
                year = int(row['year'])
                status = 'Available'  # Default status for new books

                cursor.execute(
                    "INSERT INTO books (title, author, category, year, status) VALUES (%s, %s, %s, %s, %s)",
                    (title, author, category, year, status)
                )
            conn.commit()
            cursor.close()
            conn.close()
            print(f"Successfully loaded {len(df)} books from {csv_file}")
    except Exception as e:
        print(f"Error loading books from CSV: {e}")

# Run CSV data load once when the app starts
with app.app_context():
    load_books_from_csv()

# Home page
@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')

# Register page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmpassword')

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return render_template('register.html')

        conn = get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                # Check if email already exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash("Email already registered. Please use a different email or login.", "danger")
                    return render_template('register.html')

                cursor.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                    (fullname, email, password, "student")  # Storing plain password as per your context, but hashing is recommended
                )
                conn.commit()
                flash("Registration successful! Please login.", "success")
                return redirect(url_for('login'))
            except Error as e:
                print(f"Error during registration: {e}")
                flash("Registration failed due to a database error.", "danger")
            finally:
                if conn and conn.is_connected():
                    cursor.close()
                    conn.close()
        else:
            flash("Could not connect to the database. Please try again later.", "danger")

    return render_template('register.html')

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()

        conn = get_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
                user = cursor.fetchone()

                if user:
                    session['logged_in'] = True
                    session['user_id'] = user['id']
                    session['username'] = user['name']
                    session['role'] = user['role']
                    flash(f"Welcome, {user['name']}!", "success")
                    return redirect(url_for('search'))  # Redirect to search page after login
                else:
                    flash("Invalid email or password.", "danger")
            except Error as e:
                print(f"Error during login: {e}")
                flash("Login failed due to a database error.", "danger")
            finally:
                if conn and conn.is_connected():
                    cursor.close()
                    conn.close()
        else:
            flash("Could not connect to the database. Please try again later.", "danger")

    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

# Search page
@app.route('/search', methods=['GET', 'POST'])
def search():
    books = []
    search_query = ""
    category_filter = ""
    availability_filter = ""

    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            query_parts = []
            params = []

            if request.method == 'POST':
                search_query = request.form.get('search_query', '').strip()
                category_filter = request.form.get('categoryFilter', '').strip()
                availability_filter = request.form.get('availabilityFilter', '').strip()

                if search_query:
                    query_parts.append("(LOWER(title) LIKE %s OR LOWER(author) LIKE %s OR LOWER(category) LIKE %s)")
                    search_query_lower = search_query.lower()
                    params.extend([f'%{search_query_lower}%', f'%{search_query_lower}%', f'%{search_query_lower}%'])
                if category_filter and category_filter != "All Categories":
                    query_parts.append("category = %s")
                    params.append(category_filter)
                if availability_filter:
                    query_parts.append("status = %s")
                    params.append(availability_filter)

            base_query = "SELECT * FROM books"
            if query_parts:
                base_query += " WHERE " + " AND ".join(query_parts)

            cursor.execute(base_query, tuple(params))
            books = cursor.fetchall()

        except Error as e:
            print(f"Error during search: {e}")
            flash("Error retrieving books.", "danger")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    else:
        flash("Could not connect to the database to search books.", "danger")

    return render_template('search.html', books=books, search_query=search_query,
                           category_filter=category_filter, availability_filter=availability_filter)

# Admin page (for viewing all books)
@app.route('/admin_panel')
def admin_panel():
    # Basic check for admin role (can be enhanced with decorators)
    if 'logged_in' not in session or session.get('role') != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('login'))

    books = []
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM books")
            books = cursor.fetchall()
        except Error as e:
            print(f"Error fetching books for admin: {e}")
            flash("Error retrieving books for admin panel.", "danger")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    else:
        flash("Could not connect to the database for admin panel.", "danger")

    return render_template('admin.html', books=books)


if __name__ == '__main__':
    app.run(debug=True)