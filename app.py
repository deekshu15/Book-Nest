from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import Error
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'  # ⚠️ Replace with strong key in production


# -------------------- DB CONNECTION --------------------
def get_connection():
    try:
        host = os.getenv("DB_HOST", "localhost")
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "deekshu15@2006")
        database = os.getenv("DB_NAME", "library")
        port = int(os.getenv("DB_PORT", 3306))

        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port
        )
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None


# -------------------- LOAD CSV INTO DB --------------------
def load_books_from_csv():
    csv_file = 'Departmentwise BooksData.csv'
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.")
        return

    try:
        df = pd.read_csv(csv_file)

        df.rename(columns={
            'Department': 'Department',
            'Author': 'Author',
            'Title': 'Title',
            'Year': 'Year'
        }, inplace=True)

        df = df.dropna(subset=['Title', 'Author', 'Department', 'Year'])

        def safe_int(x):
            try:
                return int(x)
            except:
                return None

        df['Year'] = df['Year'].apply(safe_int)
        df = df.dropna(subset=['Year'])

        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM books")
            conn.commit()
            print("Cleared old books.")

            for _, row in df.iterrows():
                cursor.execute(
                    "INSERT INTO books (Title, Author, Department, Year, Status) VALUES (%s, %s, %s, %s, %s)",
                    (row['Title'], row['Author'], row['Department'], int(row['Year']), 'Available')
                )
            conn.commit()
            cursor.close()
            conn.close()
            print(f"Loaded {len(df)} books.")
    except Exception as e:
        print(f"Error loading CSV: {e}")


with app.app_context():
    load_books_from_csv()


# -------------------- ROUTES --------------------
@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')


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
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash("Email already registered.", "danger")
                    return render_template('register.html')

                cursor.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                    (fullname, email, password, "student")
                )
                conn.commit()
                flash("Registration successful! Please login.", "success")
                return redirect(url_for('login'))
            except Error as e:
                print(f"Error: {e}")
                flash("Database error during registration.", "danger")
            finally:
                cursor.close()
                conn.close()
        else:
            flash("Could not connect to DB.", "danger")

    return render_template('register.html')


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
                    return redirect(url_for('search'))
                else:
                    flash("Invalid email or password.", "danger")
            except Error as e:
                print(f"Error: {e}")
                flash("Database error during login.", "danger")
            finally:
                cursor.close()
                conn.close()
        else:
            flash("Could not connect to DB.", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))


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
                    query_parts.append("(LOWER(Title) LIKE %s OR LOWER(Author) LIKE %s OR LOWER(Department) LIKE %s)")
                    sq = search_query.lower()
                    params.extend([f"%{sq}%", f"%{sq}%", f"%{sq}%"])
                if category_filter and category_filter != "All Categories":
                    query_parts.append("Department = %s")
                    params.append(category_filter)
                if availability_filter:
                    query_parts.append("Status = %s")
                    params.append(availability_filter)

            base_query = """
                SELECT 
                    Title AS title,
                    Author AS author,
                    Department AS department,
                    Year AS year,
                    Status AS status
                FROM books
            """
            if query_parts:
                base_query += " WHERE " + " AND ".join(query_parts)

            cursor.execute(base_query, tuple(params))
            books = cursor.fetchall()
        except Error as e:
            print(f"Error: {e}")
            flash("Database error during search.", "danger")
        finally:
            cursor.close()
            conn.close()
    else:
        flash("Could not connect to DB.", "danger")

    return render_template('search.html',
                           books=books,
                           search_query=search_query,
                           category_filter=category_filter,
                           availability_filter=availability_filter)


@app.route('/admin_panel')
def admin_panel():
    if 'logged_in' not in session or session.get('role') != 'admin':
        flash("Admins only.", "danger")
        return redirect(url_for('login'))

    books = []
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    Title AS title,
                    Author AS author,
                    Department AS department,
                    Year AS year,
                    Status AS status
                FROM books
            """)
            books = cursor.fetchall()
        except Error as e:
            print(f"Error: {e}")
            flash("Database error in admin panel.", "danger")
        finally:
            cursor.close()
            conn.close()
    else:
        flash("Could not connect to DB.", "danger")

    return render_template('admin.html', books=books)


if __name__ == '__main__':
    app.run(debug=True)