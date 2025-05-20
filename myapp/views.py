from django.shortcuts import render, redirect, get_object_or_404
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import check_password
from .models import UserRole
from django.contrib.auth.models import AnonymousUser

def index(request):
    return render(request, 'index.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        try:
            user = UserRole.objects.get(email=email)
            if check_password(password, user.password_hash):
                request.session['user_id'] = user.id
                request.session['user_role'] = user.role
                messages.success(request, f'Welcome, {user.name}!')
                return redirect('home')
            else:
                messages.error(request, 'Invalid password.')
        except UserRole.DoesNotExist:
            messages.error(request, 'User does not exist.')
    return render(request, 'login.html')

from django.utils.timezone import now
from datetime import date

from datetime import date
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import UserRole, Task

def dashboard(request):
    user_id = request.session.get('user_id')
    if not user_id:
        messages.warning(request, 'Please login first.')
        return redirect('login')

    try:
        user = UserRole.objects.get(id=user_id)
    except UserRole.DoesNotExist:
        return redirect('login')

    context = {'user': user}

    if user.role == 'Manager':
        total_tasks = Task.objects.filter(created_by=user).count()
        pending_tasks = Task.objects.filter(created_by=user, status='Pending').count()
        in_progress_tasks = Task.objects.filter(created_by=user, status='In Progress').count()
        completed_tasks = Task.objects.filter(created_by=user, status='Completed').count()
        overdue_tasks = Task.objects.filter(
            created_by=user,
            deadline__lt=date.today()
        ).exclude(status='Completed')
        completed_percent = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        context.update({
            'total_tasks': total_tasks,
            'pending_tasks': pending_tasks,
            'in_progress_tasks': in_progress_tasks,
            'completed_tasks': completed_tasks,
            'overdue_tasks': overdue_tasks,
            'completed_percent': completed_percent,
        })

        return render(request, 'manager_dashboard.html', context)

    elif user.role == 'Member':
        # Tasks assigned to member
        assigned_tasks = Task.objects.filter(assigned_to=user)

        # Calculate task counts by status for chart
        total_tasks = assigned_tasks.count()
        pending_tasks = assigned_tasks.filter(status='Pending').count()
        in_progress_tasks = assigned_tasks.filter(status='In Progress').count()
        completed_tasks = assigned_tasks.filter(status='Completed').count()
        overdue_tasks = assigned_tasks.filter(
            deadline__lt=date.today()
        ).exclude(status='Completed')

        completed_percent = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        context.update({
            'assigned_tasks': assigned_tasks,
            'total_tasks': total_tasks,
            'pending_tasks': pending_tasks,
            'in_progress_tasks': in_progress_tasks,
            'completed_tasks': completed_tasks,
            'overdue_tasks': overdue_tasks,
            'completed_percent': completed_percent,
        })

        return render(request, 'member_dashboard.html', context)

    else:
        return render(request, 'index.html')



def logout_view(request):
    request.session.flush()
    messages.success(request, 'You have been logged out.')
    return redirect('login')



from django.core.mail import send_mail
from django.shortcuts import render, redirect
from .models import Task, UserRole
from .forms import TaskForm
from django.contrib import messages

def add_task(request):
    if not request.session.get('user_id'):
        return redirect('login')

    creator = UserRole.objects.get(id=request.session['user_id'])

    if creator.role != 'Manager':
        messages.error(request, "Only managers can add tasks.")
        return redirect('home')

    if request.method == 'POST':
        form = TaskForm(request.POST, manager=creator)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = creator
            task.save()

            # Send email notification to assigned member
            if task.assigned_to and task.assigned_to.email:
                subject = f"New Task Assigned: {task.title}"
                message = (
                    f"Hello {task.assigned_to.name},\n\n"
                    f"You have been assigned a new task by {creator.name}.\n\n"
                    f"Title: {task.title}\n"
                    f"Description: {task.description or 'No description'}\n"
                    f"Priority: {task.priority}\n"
                    f"Deadline: {task.deadline if task.deadline else 'No deadline'}\n\n"
                    f"Please log in to the system to view and manage your tasks.\n\n"
                    f"Best regards,\n"
                    f"Task Management System with Role-Based Access Control (RBAC) System"
                )
                send_mail(
                    subject,
                    message,
                    None,  # From email (uses DEFAULT_FROM_EMAIL)
                    [task.assigned_to.email],
                    fail_silently=False,
                )

            messages.success(request, "Task created successfully.")
            return redirect('view_tasks')
    else:
        form = TaskForm(manager=creator)

    return render(request, 'add_task.html', {'form': form})



from django.db.models import Q, Count
from django.http import HttpResponse
import csv

def view_tasks(request):
    if not request.session.get('user_id'):
        return redirect('login')

    user = UserRole.objects.get(id=request.session['user_id'])

    # Base queryset depends on role
    if user.role == 'Manager':
        qs = Task.objects.filter(created_by=user)
    else:
        qs = Task.objects.filter(assigned_to=user)

    # Filters from GET params
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    deadline = request.GET.get('deadline', '')

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(assigned_to__name__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if deadline:
        qs = qs.filter(deadline=deadline)

    tasks = qs.order_by('deadline')

    # Task stats
    stats = {
        'total': tasks.count(),
        'pending': tasks.filter(status='Pending').count(),
        'in_progress': tasks.filter(status='In Progress').count(),
        'completed': tasks.filter(status='Completed').count(),
    }

    return render(request, 'view_tasks.html', {'tasks': tasks, 'stats': stats})


def export_tasks_csv(request):
    if not request.session.get('user_id'):
        return redirect('login')

    user = UserRole.objects.get(id=request.session['user_id'])

    if user.role == 'Manager':
        qs = Task.objects.filter(created_by=user)
    else:
        qs = Task.objects.filter(assigned_to=user)

    # Apply same filters as view_tasks
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    deadline = request.GET.get('deadline', '')

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(assigned_to__name__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if deadline:
        qs = qs.filter(deadline=deadline)

    tasks = qs.order_by('deadline')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tasks_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Title', 'Description', 'Priority', 'Status', 'Deadline', 'Assigned To'])

    for task in tasks:
        writer.writerow([
            task.title,
            task.description,
            task.priority,
            task.status,
            task.deadline,
            task.assigned_to.name if task.assigned_to else ''
        ])

    return response



def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if not request.session.get('user_id') or request.session['user_id'] != task.created_by.id:
        messages.error(request, "You don't have permission to edit this task.")
        return redirect('view_tasks')

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated successfully.")
            return redirect('view_tasks')
    else:
        form = TaskForm(instance=task)

    return render(request, 'edit_task.html', {'form': form, 'task': task})


def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.session.get('user_id') == task.created_by.id:
        task.delete()
        messages.success(request, "Task deleted.")
    else:
        messages.error(request, "You are not allowed to delete this task.")
    return redirect('view_tasks')


from django.db.models import Q
from django.http import HttpResponse
import csv
from datetime import datetime

def member_tasks(request):
    user_id = request.session.get('user_id')
    if not user_id:
        messages.warning(request, 'Please login first.')
        return redirect('login')

    try:
        user = UserRole.objects.get(id=user_id)
    except UserRole.DoesNotExist:
        return redirect('login')

    if user.role != 'Member':
        return redirect('index')

    tasks = Task.objects.filter(assigned_to=user)

    # Filters from GET params
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    deadline = request.GET.get('deadline', '')

    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(assigned_to__name__icontains=search)
        )
    if status:
        tasks = tasks.filter(status=status)
    if priority:
        tasks = tasks.filter(priority=priority)
    if deadline:
        tasks = tasks.filter(deadline=deadline)

    # Task stats
    stats = {
        'total': tasks.count(),
        'pending': tasks.filter(status='Pending').count(),
        'in_progress': tasks.filter(status='In Progress').count(),
        'completed': tasks.filter(status='Completed').count(),
    }

    # Export CSV
    if 'export' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="member_tasks.csv"'
        writer = csv.writer(response)
        writer.writerow(['Title', 'Description', 'Priority', 'Status', 'Deadline', 'Assigned To'])

        for task in tasks:
            writer.writerow([
                task.title,
                task.description,
                task.priority,
                task.status,
                task.deadline,
                task.assigned_to.name,
            ])
        return response

    context = {
        'user': user,
        'tasks': tasks,
        'stats': stats,
        'request': request,
        'search': search,
        'status': status,
        'priority': priority,
        'deadline': deadline,
    }
    return render(request, 'member_tasks.html', context)


def member_edit_task_status(request, task_id):
    user_id = request.session.get('user_id')
    if not user_id:
        messages.warning(request, 'Please login first.')
        return redirect('login')

    try:
        user = UserRole.objects.get(id=user_id)
    except UserRole.DoesNotExist:
        return redirect('login')

    try:
        task = Task.objects.get(id=task_id, assigned_to=user)
    except Task.DoesNotExist:
        messages.error(request, 'Task not found or access denied.')
        return redirect('member_tasks')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['Pending', 'In Progress', 'Completed']:
            task.status = new_status
            task.save()
            messages.success(request, 'Task status updated.')
        else:
            messages.error(request, 'Invalid status value.')
        return redirect('member_tasks')

    return render(request, 'member_edit_task.html', {'task': task})
