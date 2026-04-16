from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vacation.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='employee')
    department = db.Column(db.String(100))
    manages_department = db.Column(db.String(100), nullable=True)
    
    # Leave category balances - only used for employees and department heads
    vacation_days = db.Column(db.Integer, default=0)
    personal_days = db.Column(db.Integer, default=0)
    sick_days = db.Column(db.Integer, default=0)
    volunteer_days = db.Column(db.Integer, default=0)
    jury_duty_days = db.Column(db.Integer, default=0)
    
    # Used balances
    vacation_used = db.Column(db.Integer, default=0)
    personal_used = db.Column(db.Integer, default=0)
    sick_used = db.Column(db.Integer, default=0)
    volunteer_used = db.Column(db.Integer, default=0)
    jury_duty_used = db.Column(db.Integer, default=0)
    
    # Pending balances
    vacation_pending = db.Column(db.Integer, default=0)
    personal_pending = db.Column(db.Integer, default=0)
    sick_pending = db.Column(db.Integer, default=0)
    volunteer_pending = db.Column(db.Integer, default=0)
    jury_duty_pending = db.Column(db.Integer, default=0)
    
    special_consideration_requests = db.Column(db.Integer, default=0)
    
    requests = db.relationship('VacationRequest', 
                               foreign_keys='VacationRequest.user_id',
                               backref='employee', 
                               lazy=True)
    
    approved_requests = db.relationship('VacationRequest',
                                         foreign_keys='VacationRequest.approved_by',
                                         backref='approver',
                                         lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_available_days(self, category):
        """Get available days for a specific category - returns 0 for exec_director and hr"""
        if self.role == 'exec_director' or self.role == 'hr':
            return 0
        
        if category == 'vacation':
            return self.vacation_days - self.vacation_used - self.vacation_pending
        elif category == 'personal':
            return self.personal_days - self.personal_used - self.personal_pending
        elif category == 'sick':
            return self.sick_days - self.sick_used - self.sick_pending
        elif category == 'volunteer':
            return self.volunteer_days - self.volunteer_used - self.volunteer_pending
        elif category == 'jury_duty':
            return self.jury_duty_days - self.jury_duty_used - self.jury_duty_pending
        return 0
    
    def request_days(self, category, days_requested):
        """Add days to pending for a specific category"""
        if self.role == 'exec_director' or self.role == 'hr':
            return
        
        if category == 'vacation':
            self.vacation_pending += days_requested
        elif category == 'personal':
            self.personal_pending += days_requested
        elif category == 'sick':
            self.sick_pending += days_requested
        elif category == 'volunteer':
            self.volunteer_pending += days_requested
        elif category == 'jury_duty':
            self.jury_duty_pending += days_requested
    
    def approve_days(self, category, days_approved):
        """Move days from pending to used for a specific category"""
        if self.role == 'exec_director' or self.role == 'hr':
            return
        
        if category == 'vacation':
            self.vacation_used += days_approved
            self.vacation_pending -= days_approved
        elif category == 'personal':
            self.personal_used += days_approved
            self.personal_pending -= days_approved
        elif category == 'sick':
            self.sick_used += days_approved
            self.sick_pending -= days_approved
        elif category == 'volunteer':
            self.volunteer_used += days_approved
            self.volunteer_pending -= days_approved
        elif category == 'jury_duty':
            self.jury_duty_used += days_approved
            self.jury_duty_pending -= days_approved
    
    def deny_days(self, category, days_denied):
        """Remove days from pending for a specific category"""
        if self.role == 'exec_director' or self.role == 'hr':
            return
        
        if category == 'vacation':
            self.vacation_pending -= days_denied
        elif category == 'personal':
            self.personal_pending -= days_denied
        elif category == 'sick':
            self.sick_pending -= days_denied
        elif category == 'volunteer':
            self.volunteer_pending -= days_denied
        elif category == 'jury_duty':
            self.jury_duty_pending -= days_denied
    
    def get_category_display(self, category):
        """Get display name for category"""
        categories = {
            'vacation': 'Vacation',
            'personal': 'Personal Day',
            'sick': 'Sick Day',
            'volunteer': 'Volunteer Work',
            'jury_duty': 'Jury Duty',
            'part_day': 'Part of Day'
        }
        return categories.get(category, category)
    
    def get_remaining_vacation_days(self):
        """Legacy method for compatibility"""
        return self.get_available_days('vacation')
    
    def get_available_vacation_days(self):
        """Legacy method for compatibility"""
        return self.get_available_days('vacation')
    
    def can_see_request(self, request):
        if self.role == 'hr':
            return True
        if self.role == 'exec_director':
            return request.employee.role == 'dept_head'
        if self.role == 'dept_head':
            if request.employee.id == self.id:
                return True
            return request.employee.department == self.manages_department and request.employee.role == 'employee'
        if self.role == 'employee':
            return request.employee.id == self.id
        return False
    
    def can_approve_request(self, request):
        if self.role == 'hr':
            return False
        if self.role == 'exec_director':
            return request.employee.role == 'dept_head'
        if self.role == 'dept_head':
            if request.employee.id == self.id:
                return False
            if request.assigned_dept_head_id == self.id:
                return True
            return False
        return False
    
    def can_see_all_users(self):
        return self.role == 'hr' or self.role == 'exec_director'
    
    def get_role_display(self):
        roles = {
            'employee': 'Employee',
            'dept_head': 'Department Head',
            'hr': 'HR Manager',
            'exec_director': 'Executive Director'
        }
        return roles.get(self.role, self.role)

class VacationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10), nullable=True)
    end_time = db.Column(db.String(10), nullable=True)
    leave_type = db.Column(db.String(20), default='full_day')
    category = db.Column(db.String(20), default='vacation')
    hours_requested = db.Column(db.Float, default=0)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    is_special_consideration = db.Column(db.Boolean, default=False)
    deduct_from_balance = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    assigned_dept_head_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    assigned_head = db.relationship('User', foreign_keys=[assigned_dept_head_id], backref='assigned_requests')
    
    def get_days_count(self):
        if self.leave_type == 'full_day':
            return (self.end_date - self.start_date).days + 1
        else:
            return self.hours_requested / 8
    
    def get_display_text(self):
        if self.leave_type == 'full_day':
            days = self.get_days_count()
            if days == 1:
                return "1 full day"
            return f"{int(days)} full days"
        else:
            if self.hours_requested == 1:
                return "1 hour"
            return f"{self.hours_requested} hours"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'employee':
        requests = VacationRequest.query.filter_by(user_id=current_user.id).order_by(VacationRequest.created_at.desc()).all()
        return render_template('employee_dashboard.html', requests=requests)
    
    elif current_user.role == 'dept_head':
        own_requests = VacationRequest.query.filter_by(user_id=current_user.id).order_by(VacationRequest.created_at.desc()).all()
        assigned_requests = VacationRequest.query.filter_by(
            assigned_dept_head_id=current_user.id,
            status='pending'
        ).order_by(VacationRequest.created_at.desc()).all()
        department_employees = User.query.filter_by(department=current_user.manages_department, role='employee').all()
        employee_ids = [emp.id for emp in department_employees]
        all_employee_requests = VacationRequest.query.filter(
            VacationRequest.user_id.in_(employee_ids)
        ).order_by(VacationRequest.created_at.desc()).all()
        
        return render_template('dept_head_dashboard.html', 
                             own_requests=own_requests,
                             assigned_requests=assigned_requests,
                             all_employee_requests=all_employee_requests,
                             department_employees=department_employees,
                             department=current_user.manages_department)
    
    elif current_user.role == 'exec_director':
        dept_heads = User.query.filter_by(role='dept_head').all()
        dept_head_ids = [head.id for head in dept_heads]
        pending_head_requests = VacationRequest.query.filter(
            VacationRequest.user_id.in_(dept_head_ids),
            VacationRequest.status == 'pending'
        ).order_by(VacationRequest.created_at.desc()).all()
        all_head_requests = VacationRequest.query.filter(
            VacationRequest.user_id.in_(dept_head_ids)
        ).order_by(VacationRequest.created_at.desc()).all()
        
        return render_template('exec_director_dashboard.html', 
                             pending_head_requests=pending_head_requests,
                             all_head_requests=all_head_requests,
                             dept_heads=dept_heads)
    
    elif current_user.role == 'hr':
        all_requests = VacationRequest.query.order_by(VacationRequest.created_at.desc()).all()
        users = User.query.all()
        return render_template('hr_dashboard.html', 
                             all_requests=all_requests, 
                             users=users)
    
    return redirect(url_for('login'))

@app.route('/request_vacation', methods=['GET', 'POST'])
@login_required
def request_vacation():
    if request.method == 'POST':
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        leave_type = request.form.get('leave_type')
        category = request.form.get('category')
        
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        reason = request.form.get('reason')
        
        selected_dept_head_id = request.form.get('dept_head_id')
        if selected_dept_head_id:
            selected_dept_head_id = int(selected_dept_head_id)
        else:
            selected_dept_head_id = None
        
        if start_date > end_date:
            flash('End date must be after start date', 'danger')
            return redirect(url_for('request_vacation'))
        
        # Calculate days requested
        if leave_type == 'full_day':
            days_requested = (end_date - start_date).days + 1
            hours_requested = days_requested * 8
            deduct_from_balance = True
            category_value = category
        else:
            # Part of day - calculate hours
            if start_time and end_time:
                start_hour = int(start_time.split(':')[0])
                start_minute = int(start_time.split(':')[1])
                end_hour = int(end_time.split(':')[0])
                end_minute = int(end_time.split(':')[1])
                hours_per_day = (end_hour + end_minute/60) - (start_hour + start_minute/60)
                if hours_per_day < 0:
                    hours_per_day += 24
                if hours_per_day > 8:
                    hours_per_day = 8
            else:
                hours_per_day = 0
            
            days_count = (end_date - start_date).days + 1
            hours_requested = hours_per_day * days_count
            days_requested = hours_requested / 8
            deduct_from_balance = False
            category_value = 'part_day'
        
        if deduct_from_balance:
            available_days = current_user.get_available_days(category_value)
            is_special = (days_requested > available_days)
        else:
            is_special = False
        
        vacation_request = VacationRequest(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            leave_type=leave_type,
            category=category_value,
            hours_requested=hours_requested,
            reason=reason,
            is_special_consideration=is_special,
            assigned_dept_head_id=selected_dept_head_id,
            deduct_from_balance=deduct_from_balance
        )
        
        if deduct_from_balance:
            if days_requested <= available_days:
                current_user.request_days(category_value, int(days_requested))
                db.session.add(vacation_request)
                db.session.commit()
                flash(f'✅ Request submitted! {vacation_request.get_display_text()} from {current_user.get_category_display(category_value)} category.', 'success')
            else:
                db.session.add(vacation_request)
                current_user.special_consideration_requests += 1
                db.session.commit()
                flash(f'⚠️ SPECIAL CONSIDERATION: You have {available_days} days available but requested {int(days_requested)} days in {current_user.get_category_display(category_value)}.', 'warning')
        else:
            db.session.add(vacation_request)
            db.session.commit()
            flash(f'✅ Part-day request submitted! {vacation_request.get_display_text()} has been logged. This does not deduct from your balance.', 'success')
        
        return redirect(url_for('dashboard'))
    
    dept_heads = User.query.filter_by(role='dept_head').all()
    return render_template('request_vacation.html', dept_heads=dept_heads)

@app.route('/approve_request/<int:request_id>')
@login_required
def approve_request(request_id):
    vacation_request = VacationRequest.query.get_or_404(request_id)
    
    if not current_user.can_approve_request(vacation_request):
        flash('You do not have permission to approve this request', 'danger')
        return redirect(url_for('dashboard'))
    
    employee = vacation_request.employee
    days_requested = int(vacation_request.get_days_count())
    category = vacation_request.category
    
    if vacation_request.deduct_from_balance:
        if vacation_request.is_special_consideration:
            employee.approve_days(category, days_requested)
            flash(f'⚠️ SPECIAL CONSIDERATION APPROVED: {vacation_request.get_display_text()} from {employee.get_category_display(category)}.', 'warning')
        else:
            employee.approve_days(category, days_requested)
            flash(f'✅ Request approved! {vacation_request.get_display_text()} deducted from {employee.get_category_display(category)} balance.', 'success')
    else:
        flash(f'✅ Part-day request approved! {vacation_request.get_display_text()} has been logged (no balance deduction).', 'success')
    
    vacation_request.status = 'approved'
    vacation_request.approved_by = current_user.id
    vacation_request.approved_at = datetime.utcnow()
    
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/deny_request/<int:request_id>')
@login_required
def deny_request(request_id):
    vacation_request = VacationRequest.query.get_or_404(request_id)
    
    if not current_user.can_approve_request(vacation_request):
        flash('You do not have permission to deny this request', 'danger')
        return redirect(url_for('dashboard'))
    
    employee = vacation_request.employee
    days_requested = int(vacation_request.get_days_count())
    category = vacation_request.category
    
    if vacation_request.deduct_from_balance and not vacation_request.is_special_consideration:
        employee.deny_days(category, days_requested)
        flash(f'Request denied. {vacation_request.get_display_text()} returned to {employee.get_category_display(category)} balance.', 'warning')
    else:
        flash(f'Part-day request denied. {vacation_request.get_display_text()} has been logged (no balance impact).', 'warning')
    
    vacation_request.status = 'denied'
    vacation_request.approved_by = current_user.id
    vacation_request.approved_at = datetime.utcnow()
    
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/retract_request/<int:request_id>')
@login_required
def retract_request(request_id):
    vacation_request = VacationRequest.query.get_or_404(request_id)
    
    if vacation_request.user_id != current_user.id:
        flash('You can only retract your own requests', 'danger')
        return redirect(url_for('dashboard'))
    
    if vacation_request.status != 'pending':
        flash('You can only retract pending requests', 'danger')
        return redirect(url_for('dashboard'))
    
    employee = vacation_request.employee
    days_requested = int(vacation_request.get_days_count())
    category = vacation_request.category
    
    if vacation_request.deduct_from_balance and not vacation_request.is_special_consideration:
        employee.deny_days(category, days_requested)
        flash(f'✅ Request retracted! {vacation_request.get_display_text()} returned to {employee.get_category_display(category)} balance.', 'success')
    else:
        flash(f'✅ Part-day request retracted! {vacation_request.get_display_text()} has been removed (no balance impact).', 'success')
    
    db.session.delete(vacation_request)
    db.session.commit()
    
    return redirect(url_for('dashboard'))

@app.route('/register_user', methods=['GET', 'POST'])
@login_required
def register_user():
    if current_user.role != 'hr':
        flash('Only HR Manager can register new users', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        department = request.form.get('department')
        manages_department = request.form.get('manages_department')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return redirect(url_for('register_user'))
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already exists', 'danger')
            return redirect(url_for('register_user'))
        
        user = User(username=username, email=email, role=role, department=department)
        
        # Only set vacation days for employees and department heads
        if role == 'dept_head':
            user.vacation_days = 25
            user.personal_days = 5
            user.sick_days = 5
            user.volunteer_days = 3
            user.jury_duty_days = 2
        elif role == 'employee':
            user.vacation_days = 20
            user.personal_days = 5
            user.sick_days = 5
            user.volunteer_days = 3
            user.jury_duty_days = 2
        else:
            # Executive Director and HR Manager don't need vacation days
            user.vacation_days = 0
            user.personal_days = 0
            user.sick_days = 0
            user.volunteer_days = 0
            user.jury_duty_days = 0
        
        if role == 'dept_head' and manages_department:
            user.manages_department = manages_department
        
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'User registered successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register_user.html', roles=['employee', 'dept_head', 'hr', 'exec_director'])

@app.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != 'hr':
        flash('Only HR Manager can delete users', 'danger')
        return redirect(url_for('dashboard'))
    
    user_to_delete = User.query.get_or_404(user_id)
    
    if user_to_delete.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('dashboard'))
    
    if user_to_delete.role == 'exec_director':
        flash('Cannot delete Executive Director accounts', 'danger')
        return redirect(url_for('dashboard'))
    
    username = user_to_delete.username
    
    VacationRequest.query.filter_by(user_id=user_to_delete.id).delete()
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash(f'✅ User "{username}" has been deleted successfully along with all their vacation requests.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/update_user_allocations', methods=['POST'])
@login_required
def update_user_allocations():
    if current_user.role != 'hr':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    user = User.query.get(data['user_id'])
    
    if user and (user.role == 'employee' or user.role == 'dept_head'):
        user.vacation_days = int(data['vacation'])
        user.personal_days = int(data['personal'])
        user.sick_days = int(data['sick'])
        user.volunteer_days = int(data['volunteer'])
        user.jury_duty_days = int(data['jury_duty'])
        db.session.commit()
        return jsonify({'success': True})
    elif user and (user.role == 'exec_director' or user.role == 'hr'):
        return jsonify({'success': False, 'error': 'Cannot allocate days for this role'}), 400
    
    return jsonify({'success': False, 'error': 'User not found'}), 404

def init_db():
    with app.app_context():
        db.create_all()
        
        user_count = User.query.count()
        
        if user_count == 0:
            print("No users found. Creating demo accounts...")
            
            exec_director = User(username='exec_director', email='director@company.com', 
                               role='exec_director', department='Executive')
            exec_director.set_password('director123')
            exec_director.vacation_days = 0
            exec_director.personal_days = 0
            exec_director.sick_days = 0
            exec_director.volunteer_days = 0
            exec_director.jury_duty_days = 0
            db.session.add(exec_director)
            
            hr = User(username='hr_manager', email='hr@company.com', 
                      role='hr', department='HR')
            hr.set_password('hr123')
            hr.vacation_days = 0
            hr.personal_days = 0
            hr.sick_days = 0
            hr.volunteer_days = 0
            hr.jury_duty_days = 0
            db.session.add(hr)
            
            dept_heads = [
                User(username='finance_head', email='finance@company.com', 
                    role='dept_head', department='Finance', manages_department='Finance'),
                User(username='western_head', email='western@company.com', 
                    role='dept_head', department='Western Canada', manages_department='Western Canada'),
                User(username='eastern_head', email='eastern@company.com', 
                    role='dept_head', department='Eastern Canada', manages_department='Eastern Canada'),
                User(username='shareholder_head', email='shareholder@company.com', 
                    role='dept_head', department='Shareholder Relations', manages_department='Shareholder Relations'),
                User(username='communications_head', email='communications@company.com', 
                    role='dept_head', department='Communications', manages_department='Communications'),
            ]
            
            for head in dept_heads:
                head.set_password('head123')
                head.vacation_days = 25
                head.personal_days = 5
                head.sick_days = 5
                head.volunteer_days = 3
                head.jury_duty_days = 2
                db.session.add(head)
            
            db.session.commit()
            
            employees = [
                User(username='finance_emp1', email='finance1@company.com', role='employee', department='Finance'),
                User(username='finance_emp2', email='finance2@company.com', role='employee', department='Finance'),
                User(username='western_emp1', email='western1@company.com', role='employee', department='Western Canada'),
                User(username='western_emp2', email='western2@company.com', role='employee', department='Western Canada'),
                User(username='eastern_emp1', email='eastern1@company.com', role='employee', department='Eastern Canada'),
                User(username='eastern_emp2', email='eastern2@company.com', role='employee', department='Eastern Canada'),
                User(username='shareholder_emp1', email='shareholder1@company.com', role='employee', department='Shareholder Relations'),
                User(username='shareholder_emp2', email='shareholder2@company.com', role='employee', department='Shareholder Relations'),
                User(username='comm_emp1', email='comm1@company.com', role='employee', department='Communications'),
                User(username='comm_emp2', email='comm2@company.com', role='employee', department='Communications'),
            ]
            
            for emp in employees:
                emp.set_password('employee123')
                emp.vacation_days = 20
                emp.personal_days = 5
                emp.sick_days = 5
                emp.volunteer_days = 3
                emp.jury_duty_days = 2
                db.session.add(emp)
            
            db.session.commit()
            
            print("=" * 60)
            print("✅ Demo accounts created!")
            print("=" * 60)
            print("\n👑 EXECUTIVE DIRECTOR: exec_director / director123 (No vacation days)")
            print("📊 HR MANAGER: hr_manager / hr123 (No vacation days)")
            print("\n👔 DEPARTMENT HEADS (head123):")
            print("   finance_head, western_head, eastern_head, shareholder_head, communications_head")
            print("\n👤 EMPLOYEES (employee123):")
            print("   Finance: finance_emp1, finance_emp2")
            print("   Western Canada: western_emp1, western_emp2")
            print("   Eastern Canada: eastern_emp1, eastern_emp2")
            print("   Shareholder Relations: shareholder_emp1, shareholder_emp2")
            print("   Communications: comm_emp1, comm_emp2")
            print("\n✨ LEAVE RULES:")
            print("   - Full Day leaves: Deduct from balance")
            print("   - Part of Day leaves: Logged but NO balance deduction")
            print("\n" + "=" * 60)
        else:
            print(f"✅ Database already has {user_count} users.")
        
        print("🌐 Server running at: http://localhost:5500")
        print("=" * 50)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5500)