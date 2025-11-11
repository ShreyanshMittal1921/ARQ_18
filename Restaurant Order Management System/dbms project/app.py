import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

# --- Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'restaurant.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    orders = db.relationship('Order', back_populates='customer')

class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    is_available = db.Column(db.Boolean, default=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    order_type = db.Column(db.String(20), nullable=False) # 'dine-in' or 'takeaway'
    status = db.Column(db.String(20), nullable=False, default='pending') # pending, billed, completed, cancelled
    total_bill = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    customer = db.relationship('Customer', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', cascade="all, delete-orphan")
    payments = db.relationship('Payment', back_populates='order', cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    sub_total = db.Column(db.Float, nullable=False)
    
    order = db.relationship('Order', back_populates='items')
    menu_item = db.relationship('Menu')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False) # 'cash', 'card'
    payment_status = db.Column(db.String(20), default='paid')
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    order = db.relationship('Order', back_populates='payments')

# --- Helper Function ---

def update_order_total(order_id):
    """Recalculates the total bill for an order based on its items."""
    order = db.session.get(Order, order_id)
    if order:
        order.total_bill = sum(item.sub_total for item in order.items)
        db.session.commit()

# --- Routes ---

@app.route('/')
def index():
    """Dashboard: Shows daily sales and pending orders."""
    today = date.today()
    start_of_day = datetime(today.year, today.month, today.day)
    
    # Daily Sales
    completed_orders = Order.query.filter(
        Order.status == 'completed',
        Order.created_at >= start_of_day
    ).all()
    daily_sales = sum(order.total_bill for order in completed_orders)
    
    # Pending Orders (for kitchen)
    pending_orders_count = Order.query.filter(Order.status == 'pending').count()
    
    return render_template('index.html', 
                           daily_sales=daily_sales, 
                           pending_orders_count=pending_orders_count)

@app.route('/menu', methods=['GET', 'POST'])
def menu_management():
    """Manage menu items: View all and add new."""
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        description = request.form['description']
        is_available = 'is_available' in request.form
        
        new_item = Menu(name=name, price=price, description=description, is_available=is_available)
        db.session.add(new_item)
        db.session.commit()
        return redirect(url_for('menu_management'))
        
    menu_items = Menu.query.all()
    return render_template('menu.html', menu_items=menu_items)

@app.route('/orders')
def view_orders():
    """View all recent orders."""
    orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
    return render_template('orders.html', orders=orders)

@app.route('/order/new', methods=['GET', 'POST'])
def create_order():
    """POS screen to create a new order."""
    if request.method == 'POST':
        data = request.get_json()
        
        # 1. Find or Create Customer
        customer = Customer.query.filter_by(phone=data['customerPhone']).first()
        if not customer:
            customer = Customer(name=data['customerName'], phone=data['customerPhone'])
            db.session.add(customer)
            db.session.commit() # Commit to get customer.id
            
        # 2. Create Order
        new_order = Order(
            customer_id=customer.id,
            order_type=data['orderType'],
            status='pending' # Default status
        )
        db.session.add(new_order)
        db.session.commit() # Commit to get new_order.id
        
        # 3. Create OrderItems
        total_bill = 0
        for item in data['items']:
            menu_item = db.session.get(Menu, int(item['id']))
            if menu_item:
                sub_total = menu_item.price * int(item['quantity'])
                total_bill += sub_total
                order_item = OrderItem(
                    order_id=new_order.id,
                    menu_item_id=menu_item.id,
                    quantity=int(item['quantity']),
                    sub_total=sub_total
                )
                db.session.add(order_item)
                
        # 4. Update Order Total
        new_order.total_bill = total_bill
        db.session.commit()
        
        return jsonify({'success': True, 'order_id': new_order.id})

    # GET Request
    menu_items = Menu.query.filter_by(is_available=True).all()
    customers = Customer.query.all()
    return render_template('create_order.html', menu_items=menu_items, customers=customers)

@app.route('/order/<int:order_id>')
def order_detail(order_id):
    """View details of a single order, add items, and process payment."""
    order = db.session.get(Order, order_id)
    if not order:
        return "Order not found", 404
    
    menu_items = Menu.query.filter_by(is_available=True).all()
    return render_template('order_detail.html', order=order, menu_items=menu_items)

@app.route('/order/<int:order_id>/add_item', methods=['POST'])
def add_item_to_order(order_id):
    """Add a new menu item to an existing order."""
    order = db.session.get(Order, order_id)
    if not order or order.status != 'pending': # Can only add items to pending/billed orders
        return "Cannot add items to this order", 400
        
    menu_item_id = int(request.form['menu_item_id'])
    quantity = int(request.form['quantity'])
    
    menu_item = db.session.get(Menu, menu_item_id)
    
    if menu_item and quantity > 0:
        # Check if item already exists
        existing_item = OrderItem.query.filter_by(order_id=order_id, menu_item_id=menu_item_id).first()
        if existing_item:
            existing_item.quantity += quantity
            existing_item.sub_total = existing_item.quantity * menu_item.price
        else:
            new_item = OrderItem(
                order_id=order_id,
                menu_item_id=menu_item_id,
                quantity=quantity,
                sub_total=quantity * menu_item.price
            )
            db.session.add(new_item)
        
        db.session.commit()
        update_order_total(order_id) # Recalculate total
        
    return redirect(url_for('order_detail', order_id=order_id))

@app.route('/order/<int:order_id>/pay', methods=['POST'])
def pay_for_order(order_id):
    """Process payment for an order."""
    order = db.session.get(Order, order_id)
    if not order:
        return "Order not found", 404
        
    amount = float(request.form['amount'])
    payment_method = request.form['payment_method']
    
    # Simple validation: amount must cover the bill
    if amount >= order.total_bill:
        new_payment = Payment(
            order_id=order.id,
            amount=amount,
            payment_method=payment_method
        )
        db.session.add(new_payment)
        
        # Update order status
        order.status = 'completed'
        db.session.commit()
        return redirect(url_for('view_orders'))
    else:
        # Handle partial payment or underpayment (e.g., flash a message)
        return redirect(url_for('order_detail', order_id=order_id)) # Redirect back

@app.route('/kitchen')
def kitchen_display():
    """Full-screen Kitchen Order Ticket (KOT) display."""
    return render_template('kitchen_display.html')

# --- API Routes (for JavaScript) ---

@app.route('/api/kitchen_orders')
def api_kitchen_orders():
    """API endpoint to get all pending orders for the KOT."""
    pending_orders = Order.query.filter_by(status='pending').order_by(Order.created_at.asc()).all()
    
    orders_data = []
    for order in pending_orders:
        orders_data.append({
            'id': order.id,
            'order_type': order.order_type,
            'created_at': order.created_at.strftime('%I:%M %p'),
            'items': [{'name': item.menu_item.name, 'quantity': item.quantity} for item in order.items]
        })
    return jsonify(orders_data)

@app.route('/api/order/<int:order_id>/kitchen_done', methods=['POST'])
def api_kitchen_order_done(order_id):
    """API endpoint for the KOT to mark an order as 'billed' (ready)."""
    order = db.session.get(Order, order_id)
    if order and order.status == 'pending':
        order.status = 'billed' # 'billed' means kitchen is done, ready for payment
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Order not found or not pending'}), 404


# --- Run Application ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Create database tables if they don't exist
    app.run(debug=True)