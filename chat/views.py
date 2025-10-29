from django.shortcuts import redirect, render
from django.http import JsonResponse
import uuid
import os
import time
import traceback
from dotenv import load_dotenv
from openai import OpenAI
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from chat.models import Chat, Session
from django.views.decorators.csrf import csrf_exempt
import json

# -------------------- LOAD ENV --------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("❌ ERROR: OPENAI_API_KEY not found in .env file! Put OPENAI_API_KEY=sk-... in .env next to manage.py")
    client = None
else:
    client = OpenAI(api_key=OPENAI_API_KEY)
    print("✅ OpenAI API key loaded (partial):", OPENAI_API_KEY[:6] + "..." if OPENAI_API_KEY else "None")

# -------------------- GLOBALS --------------------
session_titles = []
chats = []

def generate_uuid():
    return str(uuid.uuid4())

# -------------------- HOME --------------------
def home(request):
    # Home page is your landing page
    return render(request, "home.html")

# -------------------- LOGIN --------------------
def user_login(request):
    # if request.user.is_authenticated:
    #     return redirect("chatbot")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("chatbot")
        else:
            return render(request, "login.html", {"error": "Invalid username or password"})

    return render(request, "login.html")

# -------------------- REGISTER --------------------
def Signup(request):
    # if request.user.is_authenticated:
    #     return redirect("chatbot")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        password2 = request.POST.get("password2")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")

        if password != password2:
            return render(request, "signup.html", {"error": "Passwords do not match"})
        if User.objects.filter(username=username).exists():
            return render(request, "signup.html", {"error": "Username already exists"})

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        login(request, user)
        return redirect("chatbot")

    return render(request, "signup.html")

# -------------------- LOGOUT --------------------
def user_logout(request):
    logout(request)
    return redirect("home.html")  # ✅ fixed: redirect to 'login' route, not 'login.html'

# -------------------- CHATBOT CORE --------------------
@login_required(login_url="login")
def chatbot(request):
    return render(request, "index.html")

def _call_openai_with_fallbacks(message, models=None, retries=2, backoff=1.0, timeout=15):
    """Try multiple models and retry logic."""
    if client is None:
        raise RuntimeError("OpenAI client not initialized. Check OPENAI_API_KEY in .env")

    if models is None:
        models = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]

    last_exc = None
    for model in models:
        for attempt in range(1, retries + 1):
            try:
                print(f"🔁 Trying model={model}, attempt={attempt}")
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": message},
                    ],
                    temperature=0.7,
                    max_tokens=300,
                    timeout=timeout,
                )
                if resp and getattr(resp, "choices", None):
                    choice = resp.choices[0]
                    reply = getattr(getattr(choice, "message", None), "content", None)
                    if not reply:
                        reply = getattr(choice, "text", None)
                    if not reply:
                        raise RuntimeError("OpenAI response missing content")
                    return reply.strip()
                else:
                    raise RuntimeError("Empty response from OpenAI")
            except Exception as e:
                last_exc = e
                print(f"❌ OpenAI attempt failed for model={model} (attempt {attempt}): {e}")
                traceback.print_exc()
                time.sleep(backoff * attempt)
        print(f"⚠️ Switching to next model fallback (after failures): {model}")

    raise last_exc if last_exc else RuntimeError("OpenAI call failed without exception")

def generate_chatbot_response(message):
    """Generate reply or return detailed error."""
    try:
        print("💬 Sending message to OpenAI:", message)
        reply = _call_openai_with_fallbacks(message)
        print("✅ OpenAI reply:", reply[:200])
        return reply
    except Exception as e:
        print("❌ Final OpenAI error:", e)
        traceback.print_exc()
        return f"AI: Sorry, I could not respond. Error: {e}"

# -------------------- API --------------------
@csrf_exempt
def get_chatbot_response(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            user_message = data.get("message", "").strip()
        except Exception:
            user_message = ""

        if not user_message:
            return JsonResponse({"reply": "Please enter a message."})

        chatbot_response = generate_chatbot_response(user_message)
        chat = Chat(id=generate_uuid(), message=user_message, response=chatbot_response)
        chats.append(chat)
        session_titles.append(user_message)

        return JsonResponse({"reply": chatbot_response})

    return redirect("chatbot")

# -------------------- SESSIONS --------------------
@login_required(login_url="login")
def save_chat(request):
    title = session_titles[0][:50] if session_titles else "Untitled Chat"
    session = Session(id=generate_uuid(), title=title, user=request.user)
    session.save()

    for c in chats:
        c.session = session
        c.save()

    chats.clear()
    session_titles.clear()
    return redirect("chatbot")

@login_required(login_url="login")
def load_chats(request, session_id):
    session = Session.objects.get(id=session_id)
    session_titles.clear()
    session_titles.append(session.title)

    user_chats = Chat.objects.filter(session=session)
    chats.extend(user_chats)
    return render(request, "index.html", {"chats": user_chats, "load": True})

@login_required(login_url="login")
def delete_session(request, session_id):
    session = Session.objects.get(id=session_id)
    session.delete()
    return redirect("history", request.user.username)

@login_required(login_url="login")
def history(request, username):
    user = User.objects.get(username=username)
    sessions = Session.objects.filter(user=user)
    return render(request, "chats.html", {"sessions": sessions})

@login_required(login_url="login")
def new_chat(request):
    session_titles.clear()
    chats.clear()
    return redirect("chatbot")
