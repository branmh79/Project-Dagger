# Project Dagger

A Flask web application for processing real estate CSV data and filtering VA financing information using Firebase.

## Features

- CSV file upload and processing
- Firebase Realtime Database integration
- VA financing data filtering
- Multiple export formats (Filtered VA CSV, USPS CSV)
- Batch processing for large datasets
- Modern, responsive UI

## Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Firebase**:
   - Download your Firebase service account key as `firebase_config.json`
   - Place it in the root directory

3. **Run the application**:
   ```bash
   python main.py
   ```

4. **Access the application**: http://localhost:5000

## Deployment to Render

### Prerequisites

1. **Firebase Project**: Set up a Firebase Realtime Database
2. **Service Account Key**: Generate and download your Firebase service account JSON

### Deployment Steps

1. **Push your code to GitHub**

2. **Create Render Web Service**:
   - Go to [render.com](https://render.com)
   - Create new Web Service
   - Connect your GitHub repository
   - Use the following settings:
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn main:app --config gunicorn_config.py`

3. **Set Environment Variables**:
   - `FIREBASE_DATABASE_URL`: Your Firebase database URL
   - `FIREBASE_SERVICE_ACCOUNT`: Your Firebase service account JSON (as string)

4. **Add Logo**:
   - Place your `logo.png` file in the `static/` directory
   - The logo should be 200px wide for optimal display

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FIREBASE_DATABASE_URL` | Your Firebase Realtime Database URL | `https://your-project.firebaseio.com` |
| `FIREBASE_SERVICE_ACCOUNT` | Firebase service account JSON (as string) | `{"type": "service_account", ...}` |

## File Structure

```
Project-Dagger/
├── app/
│   ├── __init__.py          # Flask app factory
│   └── routes.py            # Application routes and logic
├── templates/
│   ├── index.html           # Upload interface
│   └── finished.html        # Results page
├── static/
│   └── logo.png            # Application logo
├── main.py                 # Application entry point
├── firebase_init.py        # Firebase initialization
├── gunicorn_config.py      # Production server config
├── render.yaml             # Render deployment config
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Usage

1. **Upload CSV**: Use the web interface to upload your real estate CSV file
2. **Processing**: The app will process the data and store it in Firebase
3. **Filtering**: VA financing data is automatically filtered
4. **Export**: Download filtered data in various formats

## Database Structure

- **RealEstate**: Raw uploaded data
- **FilteredVA**: Properties with VA financing
- **CurrentVA**: Current VA properties with matching close dates

## License

© 2024 Foxtrot Company. All Rights Reserved. 