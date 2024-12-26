from flask import Blueprint, render_template, request, jsonify, redirect, url_for, make_response
import pandas as pd
from io import StringIO
from firebase_admin import db
import time  # Import the time module
import csv
from datetime import datetime
import re

main = Blueprint('main', __name__)

# Landing page route
@main.route('/')
def index():
    return render_template('index.html')

# Upload CSV files and store data in Firebase with timing and entry count
from flask import redirect, url_for

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

    # Store data in Firebase
    try:
        total_entries_all = save_to_firebase(data1, "ALL")
        total_entries_va = save_to_firebase(data2, "VA")
        total_entries = total_entries_all + total_entries_va
        print(f"ALL entries: {total_entries_all}, VA entries: {total_entries_va}, Total: {total_entries}")
    except Exception as e:
        return jsonify({'error': f'Error saving to Firebase: {str(e)}'}), 500

    # Populate CurrentVA after data is stored
    try:
        current_va_count = populate_current_va()
        print(f"CurrentVA entries: {current_va_count}")
    except Exception as e:
        return jsonify({'error': f'Error populating CurrentVA: {str(e)}'}), 500

    end_time = time.time()  # Stop the timer
    duration = end_time - start_time  # Calculate the duration in seconds

    # Redirect to finished after all operations
    return redirect(url_for('main.finished', time_taken=duration, total_entries=total_entries, current_va_count=current_va_count))



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

    # Perform a single batch write
    ref.update(batch_data)

    return len(batch_data)


def sanitize_address(address): # used for apartment parsing
    return address.replace('#', '')

def populate_current_va():
    # Reference the database nodes
    all_ref = db.reference('ALL').child('Addresses')
    va_ref = db.reference('VA').child('Addresses')
    current_va_ref = db.reference('CurrentVA')

    # Fetch data from ALL and VA nodes
    all_data = all_ref.get() or {}
    va_data = va_ref.get() or {}

    # Prepare data for CurrentVA
    current_va_data = {}

    for address, va_entry in va_data.items():
        # Get most recent Close Date in VA
        va_close_dates = va_entry.get('CloseDates', [])
        if not va_close_dates:
            continue
        va_most_recent_date = max(va_close_dates)

        # Check if the address exists in ALL
        all_entry = all_data.get(address)
        if not all_entry:
            continue

        # Get most recent Close Date in ALL
        all_close_dates = all_entry.get('CloseDates', [])
        if not all_close_dates:
            continue
        all_most_recent_date = max(all_close_dates)

        # Check if the most recent Close Date matches
        if va_most_recent_date == all_most_recent_date:
            # Initialize sub-node counter
            if address not in current_va_data:
                current_va_data[address] = {}

            next_index = len(current_va_data[address]) + 1
            current_va_data[address][str(next_index)] = {
                "Details": va_entry.get("Details", {}),
                "CloseDates": va_close_dates
            }

    # Write matching entries to CurrentVA
    current_va_ref.set(current_va_data)
    
    total_published = sum(len(entries) for entries in current_va_data.values())
    print(f"Total entries published to CurrentVA: {total_published}")
    
    return len(current_va_data)



def generate_usps_csv():
    # Reference the CurrentVA node
    current_va_ref = db.reference('CurrentVA')
    current_va_data = current_va_ref.get() or {}

    # Prepare the CSV data
    csv_data = []
    for address, entries in current_va_data.items():
        # Check if entries is a list or a dictionary
        if isinstance(entries, list):
            entries = {str(i): entry for i, entry in enumerate(entries) if entry}  # Convert list to dict-like structure

        for _, entry in entries.items():
            details = entry.get("Details", {})
            street_number = str(details.get('Street Number', '')).strip()
            street_name = str(details.get('Street Name', '')).strip()
            street_suffix = str(details.get('Street Suffix', '')).strip()
            full_address = str(details.get('Full Address', '')).strip()
            city = str(details.get('City', '')).strip()
            state = str(details.get('State Or Province', '')).strip()
            zip_code = str(details.get('Zip Code', '')).strip()

            # Skip Street Suffix if it is "N/A"
            if street_suffix == "N/A":
                street_suffix = ""

            # Handle addresses with Unit#
            if '#' in full_address:
                # Split the full address into base address and unit number
                _, unit_number = full_address.split('#', 1)
                # Reconstruct the full address
                sanitized_full_address = f"{street_number} {street_name} {street_suffix}".strip()
                sanitized_full_address = f"{sanitized_full_address} Unit#{unit_number.strip()}"
            else:
                # Address without Unit#
                sanitized_full_address = f"{street_number} {street_name} {street_suffix}".strip()

            # Format the full USPS-compliant address
            formatted_address = f"{sanitized_full_address}, {city}, {state} {zip_code}, UNITED STATES"

            # Append to CSV data
            csv_data.append({
                "Address": formatted_address,
                "Type": str(details.get("Type", "Unknown")).strip()
            })

    # Generate dynamic filename with today's date
    today_date = datetime.now().strftime("%m-%d-%Y")  # Format: MM-DD-YYYY
    filename = f"VAOwnedProperties {today_date}.csv"

    # Generate CSV response
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["Address", "Type"])
    writer.writeheader()
    writer.writerows(csv_data)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv"
    return response




@main.route('/wipe_database', methods=['POST'])
def wipe_database():
    try:
        # Reference the root of the database
        db.reference('/').delete()
        print("Database wiped successfully.")
        return redirect(url_for('main.index'))  # Redirect to the home page
    except Exception as e:
        return jsonify({'error': f'Error wiping database: {str(e)}'}), 500


@main.route('/finished')
def finished():
    time_taken = request.args.get('time_taken', 0, type=float)
    total_entries = request.args.get('total_entries', 0, type=int)
    current_va_count = request.args.get('current_va_count', 0, type=int)
    return render_template(
        'finished.html',
        time_taken=f'{time_taken:.2f}',
        total_entries=total_entries,
        current_va_count=current_va_count
    )

@main.route('/download_current_va_csv', methods=['GET'])
def download_current_va_csv():
    try:
        return generate_usps_csv()
    except Exception as e:
        return jsonify({'error': f'Error generating CSV: {str(e)}'}), 500



