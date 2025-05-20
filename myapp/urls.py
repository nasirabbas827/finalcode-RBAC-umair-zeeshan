from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.dashboard, name='home'),  
    path('add-task/', views.add_task, name='add_task'),
    path('view-tasks/', views.view_tasks, name='view_tasks'),
    path('tasks/export_csv/', views.export_tasks_csv, name='export_tasks_csv'),
    path('edit-task/<int:task_id>/', views.edit_task, name='edit_task'),
    path('delete-task/<int:task_id>/', views.delete_task, name='delete_task'),
    path('member/tasks/', views.member_tasks, name='member_tasks'),
    path('member/tasks/edit/<int:task_id>/', views.member_edit_task_status, name='member_edit_task_status'),
    
]
