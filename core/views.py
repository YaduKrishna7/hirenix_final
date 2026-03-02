from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from jobs.models import Job, Application
from django.contrib import messages

def home_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')

@login_required
def dashboard_view(request):
    if request.user.role == 'COMPANY':
        jobs = Job.objects.filter(company=request.user).order_by('-created_at')
        
        # Group applications by job, storing them in a dictionary or just passing the jobs if we prefetch them
        from django.db.models import Prefetch
        
        # Prefetch applications ordered by ATS score (highest first)
        jobs_with_apps = Job.objects.filter(company=request.user).prefetch_related(
            Prefetch(
                'applications',
                queryset=Application.objects.order_by('-ats_score', '-created_at'),
                to_attr='ranked_applications'
            )
        ).order_by('-created_at')
        # Pass the total applications count back to the template
        applications_count = Application.objects.filter(job__company=request.user).count()
        
        return render(request, 'core/company_dashboard.html', {
            'jobs_with_apps': jobs_with_apps, 
            'jobs': jobs, 
            'applications_count': applications_count
        })
    elif request.user.role == 'CANDIDATE':
        applications = Application.objects.filter(
            candidate=request.user
        ).select_related('job', 'job__company', 'job__company__company_profile').order_by('-created_at')
        
        context = {
            'applications': applications
        }
        return render(request, 'core/candidate_dashboard.html', context)
        
    elif request.user.role == 'HR':
        # HR dashboard for Level 3
        applications = Application.objects.filter(
            job__hr_assignee=request.user,
            status__in=[Application.Status.LEVEL3_PENDING, Application.Status.HIRED, Application.Status.REJECTED]
        ).select_related('candidate', 'job').order_by('-created_at')
        
        return render(request, 'core/hr_dashboard.html', {'applications': applications})
    elif request.user.role == 'ADMIN' or request.user.is_superuser:
        return redirect('admin:index')
    else:
        return render(request, 'core/admin_dashboard.html')

@login_required
@csrf_protect
def update_application_status(request, app_id):
    if request.method == 'POST':
        app = get_object_or_404(Application, pk=app_id)
        # Verify permissions: Only company can update up to Level 3, HR does Level 3
        if request.user.role != 'COMPANY' and request.user.role != 'HR':
            messages.error(request, "Permission denied.")
            return redirect('dashboard')
            
        new_status = request.POST.get('status')
        if new_status in dict(Application.Status.choices):
            app.status = new_status
            app.save()
            messages.success(request, f"Application status updated to {app.get_status_display()}")
            
    return redirect('dashboard')

@login_required
@csrf_protect
def hr_feedback_view(request, app_id):
    if request.user.role != 'HR' and request.user.role != 'COMPANY':
        return redirect('dashboard')
        
    app = get_object_or_404(Application, pk=app_id)
    
    if request.method == 'POST':
        action = request.POST.get('action') # 'SAVE_FEEDBACK', 'SCHEDULE_MEET', 'HIRE', 'REJECT'
        
        if action == 'SAVE_FEEDBACK':
            app.hr_feedback = request.POST.get('hr_feedback', '')
            app.save()
            messages.success(request, "Feedback saved.")
            
        elif action == 'SCHEDULE_MEET':
            meet_link = request.POST.get('meet_link', '')
            app.hr_meet_link = meet_link
            app.save()
            messages.success(request, "Meeting link sent to candidate.")
            
        elif action == 'HIRE':
            app.status = Application.Status.HIRED
            app.save()
            messages.success(request, f"Candidate {app.candidate.username} hired!")
            return redirect('dashboard')
            
        elif action == 'REJECT':
            app.status = Application.Status.REJECTED
            app.save()
            messages.info(request, f"Candidate {app.candidate.username} rejected.")
            return redirect('dashboard')
            
    return render(request, 'core/hr_feedback.html', {'app': app})
