from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import pandas as pd
from io import StringIO
from firebase_admin import db
import time  # Import the time module
import re

main = Blueprint('main', __name__)

# Landing page route
@main.route('/')
def index():
    return render_template('index.html')

# Upload CSV files and store data in Firebase with timing and entry count
from flask import redirect, url_for

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

    # Redirect to the finished page with the calculated values
    return redirect(url_for('main.finished', time_taken=duration, entries=total_entries))


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

    # Reference the Firebase Addresses node
    ref = db.reference(node_name).child('Addresses')

    # Batch updates for efficiency
    batch_data = {}

    # Loop through rows and structure data
    for index, row in data.iterrows():
        # Replace NaN values with default or empty strings
        row = row.fillna('N/A')

        full_address = row['Full Address']
        close_date = row['Close Date']

        # Determine the property type (Apartment or House)
        property_type = "Apartment" if "#" in full_address else "House"

        # Sanitize the Full Address for use as a Firebase key
        sanitized_address = sanitize_address(full_address)

        # Initialize the address node if not already in batch_data
        if sanitized_address not in batch_data:
            batch_data[sanitized_address] = {
                "Details": {
                    "Type": property_type,
                    "Full Address": full_address,
                    "County": row['County'],
                    "City": row['City'],
                    "Street Name": row['Street Name'],
                    "State Or Province": row['State Or Province'],
                    "Street Number": row['Street Number'],
                    "Street Suffix": row['Street Suffix'],
                    "Zip Code": row['Zip Code']
                },
                "CloseDates": []
            }

        # Merge Close Dates
        current_close_dates = batch_data[sanitized_address]["CloseDates"]
        if close_date not in current_close_dates:
            current_close_dates.append(close_date)
            batch_data[sanitized_address]["CloseDates"] = sorted(current_close_dates)

    # Debugging: Log batch data to verify completeness
    print(f"Total entries to write: {len(batch_data)}")

    # Perform a single batch write
    ref.update(batch_data)

    return len(batch_data)


def sanitize_address(address): # used for apartment parsing
    """
    Sanitize an address by removing '#' to make it valid as a Firebase key.
    """
    return address.replace('#', '')


@main.route('/finished')
def finished():
    time_taken = request.args.get('time_taken', 0, type=float)  # Retrieve time from query params
    entries = request.args.get('entries', 0, type=int)  # Retrieve entries from query params
    return render_template('finished.html', time_taken=f'{time_taken:.2f}', entries=entries)


