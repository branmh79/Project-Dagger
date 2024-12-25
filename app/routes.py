from flask import Blueprint, render_template, request, jsonify
import pandas as pd
from io import StringIO
from firebase_admin import db
import time  # Import the time module

main = Blueprint('main', __name__)

# Landing page route
@main.route('/')
def index():
    return render_template('index.html')

# Upload CSV files and store data in Firebase with timing and entry count
@main.route('/upload_csvs', methods=['POST'])
def upload_csvs():
    start_time = time.time()  # Start the timer

    # Retrieve files from the request
    file1 = request.files.get('csv1')
    file2 = request.files.get('csv2')

    if not file1 or not file2:
        return jsonify({'error': 'Both CSV files are required.'}), 400

    # Validate file extensions
    if not file1.filename.endswith('.csv') or not file2.filename.endswith('.csv'):
        return jsonify({'error': 'Files must be in CSV format.'}), 400

    # Read files into pandas DataFrames
    try:
        data1 = pd.read_csv(StringIO(file1.read().decode('utf-8')))
        data2 = pd.read_csv(StringIO(file2.read().decode('utf-8')))
    except Exception as e:
        return jsonify({'error': f'Error reading CSV files: {str(e)}'}), 400

    # Extract and store data in Firebase, and count total entries
    try:
        total_entries = save_to_firebase(data1, "ALL") + save_to_firebase(data2, "VA")
    except Exception as e:
        return jsonify({'error': f'Error saving to Firebase: {str(e)}'}), 500

    end_time = time.time()  # Stop the timer
    duration = end_time - start_time  # Calculate the duration in seconds

    return jsonify({
        'message': f'{duration:.2f} seconds for {total_entries} total entries'
    }), 200

# Helper function to save data to Firebase and count entries
def save_to_firebase(data, node_name):
    # Ensure required columns exist
    required_columns = [
        'Full Address', 'Close Date', 'County', 'City', 'Street Name',
        'State Or Province', 'Street Number', 'Street Suffix', 'Zip Code'
    ]
    for col in required_columns:
        if col not in data.columns:
            raise ValueError(f"Missing required column '{col}' in {node_name} CSV.")

    # Reference the Firebase node (ALL or VA)
    ref = db.reference(node_name)

    # Count the number of entries added
    entry_count = 0
    apartment_count = 0  # For numbering apartments

    # Loop through rows and save data
    for index, row in data.iterrows():
        # Replace NaN values with default or empty strings
        row = row.fillna('N/A')

        full_address = row['Full Address']

        # Determine if it's an Apartment or a House
        if "#" in full_address:
            # Save under Apartment node with a numbered key
            apartment_ref = ref.child('Apartment').child(str(apartment_count + 1))
            apartment_ref.set({
                'Full Address': full_address,
                'Close Date': row['Close Date'],
                'County': row['County'],
                'City': row['City'],
                'Street Name': row['Street Name'],
                'State Or Province': row['State Or Province'],
                'Street Number': row['Street Number'],
                'Street Suffix': row['Street Suffix'],
                'Zip Code': row['Zip Code']
            })
            apartment_count += 1
        else:
            # Save under House node with Full Address as the key
            house_ref = ref.child('House').child(
                full_address.replace('.', '').replace('$', '').replace('[', '').replace(']', '')
            )  # Clean invalid characters
            house_ref.set({
                'Close Date': row['Close Date'],
                'County': row['County'],
                'City': row['City'],
                'Street Name': row['Street Name'],
                'State Or Province': row['State Or Province'],
                'Street Number': row['Street Number'],
                'Street Suffix': row['Street Suffix'],
                'Zip Code': row['Zip Code']
            })
        entry_count += 1

    return entry_count


