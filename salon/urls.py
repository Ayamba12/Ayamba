from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.urls import reverse_lazy

app_name = 'salon'

urlpatterns = [
    # Main pages
    path('', views.index, name='index'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path("availability/<int:service_id>/", views.check_availability, name="check_availability"),

    # Service-related URLs
    path('services/<int:service_id>/', views.service_detail, name='service_detail'),
    path('services/<int:service_id>/delete/', views.delete_service, name='delete_service'),

    path('order/product/<int:service_id>/<int:subservice_id>/', views.order_product, name='order_product'),
    path('order/<int:order_id>/', views.view_order, name='view_order'),
    path('confirm-payment/<str:order_type>/<int:order_id>/', views.confirm_payment, name='confirm_payment'),

    # Appointment URLs
    path('book/<int:service_id>/', views.book_appointment, name='book_appointment'),
    path('appointments/', views.appointment_list, name='appointment_list'),
    path('appointments/<int:appointment_id>/', views.appointment_detail, name='appointment_detail'),
    path('appointments/<int:appointment_id>/confirm/', views.confirm_appointment, name='confirm_appointment'),
    path('appointments/<int:appointment_id>/cancel/', views.cancel_appointment, name='cancel_appointment'),

    # Wig URLs
    path('wig/<int:wig_id>/order/', views.order_wig, name='order_wig'),

    # Authentication URLs
    path('accounts/register/', views.register, name='register'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Password change URLs
    path('accounts/password_change/',
         auth_views.PasswordChangeView.as_view(template_name='registration/password_change.html'),
         name='password_change'),
    path('accounts/password_change/done/',
         auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'),
         name='password_change_done'),

    # Password reset URLs
    path('accounts/password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset.html',
             email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt',
             success_url=reverse_lazy('salon:password_reset_done')
         ),
         name='password_reset'),
    path('accounts/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
         name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('accounts/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),
]
