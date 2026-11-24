# Put Arundhati Nakshatra online and on your iPhone (free)

You need three free accounts: **GitHub** (stores the code), **Neon** (stores your kundalis) and **Render** (runs the app).
Total time: about 20 minutes.

## 1. Free database — Neon
1. Go to https://neon.com and sign up (no card needed).
2. Create a project (any name, choose a region near you, e.g. Singapore or Mumbai if offered).
3. On the project dashboard click **Connect** and copy the connection string. It looks like
   `postgresql://user:password@ep-xxxx.aws.neon.tech/neondb?sslmode=require`. Keep it private.

## 2. Code on GitHub
1. Go to https://github.com/new, name it `arundhati-nakshatra`, choose **Private**, click **Create repository**.
2. In Terminal, in your project folder, run (replace YOUR-USERNAME):
   ```bash
   cd ~/Downloads/Projects/Arundhati_Nakshatra
   git init
   git add .
   git commit -m "Arundhati Nakshatra"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/arundhati-nakshatra.git
   git push -u origin main
   ```
   The `.gitignore` file keeps your `.env` keys, your `data` folder and the virtual environment off GitHub.
   If Git asks you to log in, use your GitHub username and a personal access token
   (GitHub → Settings → Developer settings → Personal access tokens), or use the GitHub Desktop app instead.

## 3. Run it on Render
1. Go to https://render.com, sign up with your GitHub account.
2. Click **New → Blueprint**, pick the `arundhati-nakshatra` repository. Render reads `render.yaml`.
3. It asks for the secret values:
   - **APP_PASSWORD** — choose the password for the login screen.
   - **DATABASE_URL** — paste the Neon connection string from step 1.
   - **GEMINI_API_KEY** — optional; you can also paste it later in the app (My Profile → AI Settings).
4. Click **Apply**. The first build takes 3–6 minutes. Your app gets an address like
   `https://arundhati-nakshatra.onrender.com`.

Free plan note: the app sleeps after 15 minutes without visitors; the first visit after that takes about a minute to wake up.

## 4. Install it on your iPhone
1. Open your Render address in **Safari** on the iPhone and log in.
2. Tap the **Share** button (square with an arrow) → **Add to Home Screen** → **Add**.
3. The lotus icon appears on your home screen and opens full-screen like an app.

## First time in the app
1. Open the **Admin** tab (🔒). The first time, it asks you to **create an admin password** — only you use it.
   (Online you can instead set `ADMIN_PASSWORD` in Render's Environment settings.)
2. In **AI Assistant**, tap **Google Gemini**, paste your free key and tap **Save & test**.
3. In **Free questions**, choose how many free AI questions each kundali gets (default 3).
4. In **Question codes**, create codes (e.g. 10 questions each) to give to clients — they type the code in the chat.

## Updating the app later
Make changes on your Mac, then run `git add . && git commit -m "update" && git push`. Render redeploys automatically.

## Your existing saved kundalis
Kundalis saved on your Mac stay in the local `data` folder. The online app starts empty — re-enter the birth
details there (or ask Claude to add an import tool).
