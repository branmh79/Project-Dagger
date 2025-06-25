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
@main.route('/upload_csv', methods=['POST'])
def upload_csvs():
    start_time = time.time()  # Start the timer

    # Retrieve file from the request
    uploaded_file = request.files.get('csv')

    if not uploaded_file or not uploaded_file.filename.endswith('.csv'):
        return jsonify({'error': 'A CSV file is required.'}), 400

    # Read the file into a DataFrame in chunks for batching
    try:
        chunks = pd.read_csv(
            StringIO(uploaded_file.read().decode('utf-8')), 
            dtype=str,  # Treat all columns as strings
            low_memory=False,
            chunksize=2000  # Process 1000 rows at a time
        )
    except Exception as e:
        return jsonify({'error': f'Error reading CSV file: {str(e)}'}), 400

    # Save data to Firebase in batches
    total_entries = 0
    for chunk in chunks:
        try:
            total_entries += save_to_firebase(chunk, "RealEstate")
        except Exception as e:
            return jsonify({'error': f'Error saving to Firebase: {str(e)}'}), 500

    # Filter data and populate a new node for exporting
    try:
        filtered_count = populate_filtered_va_data()
    except Exception as e:
        return jsonify({'error': f'Error populating filtered VA data: {str(e)}'}), 500

    end_time = time.time()  # Stop the timer
    duration = end_time - start_time  # Calculate the duration in seconds

    # Redirect to finished after all operations
    return redirect(url_for('main.finished', time_taken=duration, entries=total_entries, current_va_count=filtered_count))




def sanitize_key(key):
    """Sanitize Firebase key by removing invalid characters."""
    return re.sub(r'[.$#\[\]/]', '_', str(key))

# Helper function to save data to Firebase and count entries
def save_to_firebase(data, node_name, batch_size=500):
    ref = db.reference(node_name)
    batch_data = {}
    total_written = 0

    for index, row in data.iterrows():
        row = row.fillna('N/A')  # Replace NaN values
        address = sanitize_key(row['Address'])

        if address not in batch_data:
            batch_data[address] = []
        batch_data[address].append(dict(row))

        # Write in batches
        if len(batch_data) >= batch_size:
            ref.update(batch_data)
            total_written += len(batch_data)
            batch_data = {}  # Clear batch data

    # Write any remaining data
    if batch_data:
        ref.update(batch_data)
        total_written += len(batch_data)

    return total_written



def populate_filtered_va_data():
    # Reference the RealEstate node
    ref = db.reference('RealEstate')
    data = ref.get() or {}

    # Reference the FilteredVA node
    filtered_ref = db.reference('FilteredVA')
    filtered_data = {}

    for address, entries in data.items():
        # Sort entries by CloseDate in descending order (latest first)
        entries = sorted(entries, key=lambda x: pd.to_datetime(x.get('CloseDate', ''), errors='coerce'), reverse=True)

        # Get the most recent entry
        most_recent_entry = entries[0] if entries else None

        # Skip the address if there's no valid recent entry
        if not most_recent_entry:
            continue

        # Check if the most recent entry has BuyerFinancing as "VA"
        if most_recent_entry.get('BuyerFinancing', '') == 'VA':
            # Only include the most recent entry if BuyerFinancing is VA
            filtered_data[address] = [most_recent_entry]

    # Write the filtered data back to Firebase
    filtered_ref.set(filtered_data)
    return len(filtered_data)



def generate_filtered_va_csv():
    # Reference the FilteredVA node
    ref = db.reference('FilteredVA')
    filtered_data = ref.get() or {}

    # Flatten the filtered data into rows for CSV writing
    csv_data = []
    for address, entries in filtered_data.items():
        for entry in entries:
            csv_data.append(entry)

    # Ensure there is data to generate the CSV
    if not csv_data:
        return jsonify({'error': 'No data available to generate CSV.'}), 400

    # Count the number of entries
    total_entries = len(csv_data)

    # Define the required columns and their order
    required_columns = ["Address", "City", "StateOrProvince", "PostalCode", "CountyOrParish", "MLSNumber", "BuyerFinancing"]

    # Reformat the data to include only the required columns
    formatted_data = []
    for row in csv_data:
        formatted_row = {col: row.get(col, "N/A") for col in required_columns}
        formatted_data.append(formatted_row)

    # Generate the CSV response
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=required_columns)
    writer.writeheader()
    writer.writerows(formatted_data)

    # Create the file name dynamically with the current date
    today_date = datetime.now().strftime("%m-%d-%Y")  # Format: MM-DD-YYYY
    filename = f"FilteredVA_{today_date}.csv"

    # Return the response with the CSV file and entry count
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv"

    print(f"Filtered VA CSV generated with {total_entries} entries.")  # Log the entry count

    return response, total_entries





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
            county = str(details.get('County', '')).strip()

            if ',' in county:
                county = county.split(',')[0].strip()

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

            # Add the reformatted row to the CSV data
            csv_data.append({
                "Address": sanitized_full_address,
                "City": city,
                "State": state,
                "Zip Code": zip_code,
                "County": county
            })

    # Generate dynamic filename with today's date
    today_date = datetime.now().strftime("%m-%d-%Y")  # Format: MM-DD-YYYY
    filename = f"VAOwnedProperties {today_date}.csv"

    # Generate CSV response
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["Address", "City", "State", "Zip Code", "County"])
    writer.writeheader()
    writer.writerows(csv_data)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv"
    return response






def delete_node_in_batches(node_name, batch_size=500):
    """Deletes a node's children in smaller batches to avoid size limits."""
    ref = db.reference(node_name)
    node_data = ref.get() or {}

    # Iterate through the children of the node in batches
    keys = list(node_data.keys())
    for i in range(0, len(keys), batch_size):
        batch_keys = keys[i:i + batch_size]
        print(f"Deleting batch from '{node_name}': {batch_keys}")
        for key in batch_keys:
            ref.child(key).delete()

    print(f"Node '{node_name}' wiped in batches.")


@main.route('/finished')
def finished():
    time_taken = request.args.get('time_taken', 0, type=float)
    entries = request.args.get('entries', 0, type=int)
    current_va_count = request.args.get('current_va_count', 0, type=int)
    return render_template(
        'finished.html',
        time_taken=f'{time_taken:.2f}',
        entries=entries,
        current_va_count=current_va_count
    )

@main.route('/download_filtered_va_csv', methods=['GET'])
def download_filtered_va_csv():
    # Reference the FilteredVA node
    ref = db.reference('FilteredVA')
    filtered_data = ref.get() or {}

    # Flatten the filtered data into rows for CSV writing
    csv_data = []
    for address, entries in filtered_data.items():
        for entry in entries:
            csv_data.append(entry)

    # Define the required columns and their order
    required_columns = ["Address", "City", "StateOrProvince", "PostalCode", "CountyOrParish", "MLSNumber", "BuyerFinancing"]

    # Reformat the data to include only the required columns
    formatted_data = []
    for row in csv_data:
        formatted_row = {col: row.get(col, "N/A") for col in required_columns}
        formatted_data.append(formatted_row)

    # Generate the CSV response
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=required_columns)
    writer.writeheader()
    writer.writerows(formatted_data)

    # Create the file name dynamically with the current date
    today_date = datetime.now().strftime("%m-%d-%Y")  # Format: MM-DD-YYYY
    filename = f"FilteredVA_{today_date}.csv"

    # Return the response with the CSV file
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv"
    return response

def wipe_database_in_batches(batch_size=1000):
    """
    Wipes the database in batches to avoid exceeding Firebase's size limit.
    Args:
        batch_size (int): Number of entries to delete in each batch.
    """
    # Reference the root node of the database
    ref = db.reference('/')

    # Get all data in the database
    data = ref.get() or {}

    # Iterate through top-level keys and delete in batches
    for parent_key, entries in data.items():
        parent_ref = ref.child(parent_key)
        keys = list(entries.keys())

        # Delete entries in batches
        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i:i + batch_size]
            updates = {key: None for key in batch_keys}
            parent_ref.update(updates)  # Set batch entries to None to delete them

            # Log progress
            print(f"Deleted {len(batch_keys)} entries from {parent_key}")

    print("Database wipe complete.")



@main.route('/download_current_va_csv', methods=['GET'])
def download_current_va_csv():
    try:
        return generate_usps_csv()
    except Exception as e:
        return jsonify({'error': f'Error generating CSV: {str(e)}'}), 500


@main.route('/wipe_database', methods=['POST'])
def wipe_database():
    try:
        wipe_database_in_batches(batch_size=1000)  # Adjust batch size as needed
        return jsonify({"message": "Database wiped successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500