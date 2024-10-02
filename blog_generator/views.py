from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
from pytube import YouTube
import os
import assemblyai as aai
import openai
from .models import BlogPost

# Index view - the home page. This view requires the user to be logged in.


@login_required
def index(request):
    """
    Render the home page.

    This view is only accessible to authenticated users.
    """
    return render(request, 'index.html')

# Blog generation view - this view accepts a YouTube link, transcribes it, and generates a blog post.


@csrf_exempt
def generate_blog(request):
    """
    Generate a blog post from a YouTube video transcription.

    Accepts POST requests with a JSON payload containing the YouTube link, transcribes the video using AssemblyAI,
    and generates a blog article using OpenAI's GPT-3. The blog article is saved to the database.
    """
    if request.method == 'POST':
        try:
            # Parse request body to get YouTube link
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # Fetch the YouTube title and transcription
        title = yt_title(yt_link)
        transcription = get_transcription(yt_link)

        # If transcription fails, return an error
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript"}, status=500)

        # Generate the blog content using the transcription
        blog_content = generate_blog_from_transcription(transcription)

        # If blog generation fails, return an error
        if not blog_content:
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)

        # Save the new blog article in the database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        # Return the generated blog article as a JSON response
        return JsonResponse({'content': blog_content})

    # If the request method is not POST, return a method not allowed error
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Helper function to retrieve YouTube video title


def yt_title(link):
    """
    Get the title of a YouTube video.

    :param link: YouTube video link
    :return: Title of the YouTube video
    """
    yt = YouTube(link)
    return yt.title

# Helper function to download audio from YouTube video


def download_audio(link):
    """
    Download the audio of a YouTube video and convert it to mp3.

    :param link: YouTube video link
    :return: Path to the downloaded mp3 file
    """
    yt = YouTube(link)
    video = yt.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

# Helper function to transcribe audio using AssemblyAI


def get_transcription(link):
    """
    Transcribe audio from a YouTube video using AssemblyAI.

    :param link: YouTube video link
    :return: Transcription text of the video
    """
    # Download audio from YouTube
    audio_file = download_audio(link)

    # Set AssemblyAI API key
    aai.settings.api_key = "your-assemblyai-api-key"

    # Initialize the AssemblyAI transcriber
    transcriber = aai.Transcriber()

    # Transcribe the audio file and return the text
    transcript = transcriber.transcribe(audio_file)
    return transcript.text

# Helper function to generate blog content using OpenAI GPT-3


def generate_blog_from_transcription(transcription):
    """
    Generate blog content from a transcription using OpenAI GPT-3.

    :param transcription: Transcription text of the YouTube video
    :return: Generated blog article content
    """
    # Set OpenAI API key
    openai.api_key = "your-openai-api-key"

    # Define the prompt for GPT-3
    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article. " \
             f"Ensure it reads as a proper blog article and not like a video transcript:\n\n{transcription}\n\nArticle:"

    # Generate the blog content
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        max_tokens=1000
    )

    # Return the generated blog content
    generated_content = response.choices[0].text.strip()
    return generated_content

# View to display all blogs created by the logged-in user


def blog_list(request):
    """
    List all blog articles created by the logged-in user.

    :param request: HTTP request object
    :return: Rendered HTML page with all blog articles
    """
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

# View to display details of a single blog article


def blog_details(request, pk):
    """
    Display the details of a specific blog article.

    :param request: HTTP request object
    :param pk: Primary key (ID) of the blog post
    :return: Rendered HTML page with blog article details or redirect to home if unauthorized
    """
    blog_article_detail = BlogPost.objects.get(id=pk)

    # Ensure the logged-in user owns the blog article before displaying
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

# User login view


def user_login(request):
    """
    Handle user login.

    Accepts POST requests with username and password to authenticate the user. If successful, redirects to the home page.
    """
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        # Authenticate the user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')

# User signup view


def user_signup(request):
    """
    Handle user registration.

    Accepts POST requests with username, email, password, and repeat password fields. If registration is successful,
    the user is logged in automatically and redirected to the home page.
    """
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        # Check if passwords match
        if password == repeatPassword:
            try:
                # Create and save a new user
                user = User.objects.create_user(username, email, password)
                user.save()

                # Log the user in
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = 'Passwords do not match'
            return render(request, 'signup.html', {'error_message': error_message})

    return render(request, 'signup.html')

# User logout view


def user_logout(request):
    """
    Log the user out and redirect to the home page.

    :param request: HTTP request object
    :return: Redirect to the home page
    """
    logout(request)
    return redirect('/')
