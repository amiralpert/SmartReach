// ======================
// DOGNOSIS OUTREACH AUTOMATION - DATA DOMAIN
// Spreadsheet operations and data management
// ======================

const Data = {
  /**
   * Get all contacts from spreadsheet
   */
  getAllContacts: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      
      if (!contactSheet) {
        throw new Error("ContactList sheet not found");
      }
      
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      const contacts = [];
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        // Skip empty rows
        if (!row[headers.indexOf(COLUMN_NAMES.EMAIL)]) continue;
        
        const contact = Services.createContactFromRow(row, headers, i);
        contacts.push(contact);
      }
      
      console.log(`📊 Loaded ${contacts.length} contacts from spreadsheet`);
      return contacts;
      
    } catch (error) {
      Services.logError('Data.getAllContacts', error);
      return [];
    }
  },
  
  /**
   * Get contact by email
   */
  getContactByEmail: function(email) {
    try {
      const contacts = this.getAllContacts();
      return contacts.find(c => c.email.toLowerCase() === email.toLowerCase()) || null;
      
    } catch (error) {
      Services.logError('Data.getContactByEmail', error, { email });
      return null;
    }
  },
  
  /**
   * Add new contact
   */
  addContact: function(contactData) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      
      // Check if contact already exists
      const existing = this.getContactByEmail(contactData.email);
      if (existing) {
        return { success: false, error: "Contact already exists" };
      }
      
      // Build row data
      const newRow = new Array(headers.length).fill("");
      
      // Map contact data to columns
      const mappings = {
        [COLUMN_NAMES.EMAIL]: contactData.email,
        [COLUMN_NAMES.FIRST_NAME]: contactData.firstName,
        [COLUMN_NAMES.LAST_NAME]: contactData.lastName,
        [COLUMN_NAMES.COMPANY]: contactData.company,
        [COLUMN_NAMES.TITLE]: contactData.title,
        [COLUMN_NAMES.LINKEDIN_URL]: contactData.linkedinUrl,
        [COLUMN_NAMES.MESSAGE_SEQUENCE_SHEET]: contactData.sequenceSheet,
        [COLUMN_NAMES.PAUSED]: "No",
        [COLUMN_NAMES.REPLIED_TO_EMAIL]: "No",
        [COLUMN_NAMES.REPLIED_TO_LINKEDIN]: "No"
      };
      
      for (const [columnName, value] of Object.entries(mappings)) {
        const columnIndex = headers.indexOf(columnName);
        if (columnIndex !== -1 && value !== undefined) {
          newRow[columnIndex] = value;
        }
      }
      
      // Append row
      contactSheet.appendRow(newRow);
      
      console.log(`✅ Added new contact: ${contactData.email}`);
      return { success: true };
      
    } catch (error) {
      Services.logError('Data.addContact', error, { email: contactData.email });
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Update contact data
   */
  updateContact: function(email, updates) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      // Find contact row
      let contactRowIndex = -1;
      for (let i = 1; i < data.length; i++) {
        if (data[i][headers.indexOf(COLUMN_NAMES.EMAIL)] === email) {
          contactRowIndex = i;
          break;
        }
      }
      
      if (contactRowIndex === -1) {
        return { success: false, error: "Contact not found" };
      }
      
      // Apply updates
      for (const [field, value] of Object.entries(updates)) {
        const columnIndex = headers.indexOf(field);
        if (columnIndex !== -1) {
          contactSheet.getRange(contactRowIndex + 1, columnIndex + 1).setValue(value);
        }
      }
      
      console.log(`✅ Updated contact: ${email}`);
      return { success: true };
      
    } catch (error) {
      Services.logError('Data.updateContact', error, { email });
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Delete contact
   */
  deleteContact: function(email) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      // Find contact row
      let contactRowIndex = -1;
      for (let i = 1; i < data.length; i++) {
        if (data[i][headers.indexOf(COLUMN_NAMES.EMAIL)] === email) {
          contactRowIndex = i;
          break;
        }
      }
      
      if (contactRowIndex === -1) {
        return { success: false, error: "Contact not found" };
      }
      
      // Delete row
      contactSheet.deleteRow(contactRowIndex + 1);
      
      console.log(`✅ Deleted contact: ${email}`);
      return { success: true };
      
    } catch (error) {
      Services.logError('Data.deleteContact', error, { email });
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Import contacts from CSV data
   */
  importContactsFromCSV: function(csvData) {
    console.log("📥 Importing contacts from CSV...");
    
    const results = {
      success: true,
      imported: 0,
      skipped: 0,
      errors: []
    };
    
    try {
      // Parse CSV
      const rows = Utilities.parseCsv(csvData);
      if (rows.length < 2) {
        return { success: false, error: "No data found in CSV" };
      }
      
      const csvHeaders = rows[0];
      
      // Map CSV headers to our column names
      const fieldMappings = {
        'email': COLUMN_NAMES.EMAIL,
        'first_name': COLUMN_NAMES.FIRST_NAME,
        'firstname': COLUMN_NAMES.FIRST_NAME,
        'last_name': COLUMN_NAMES.LAST_NAME,
        'lastname': COLUMN_NAMES.LAST_NAME,
        'company': COLUMN_NAMES.COMPANY,
        'title': COLUMN_NAMES.TITLE,
        'linkedin_url': COLUMN_NAMES.LINKEDIN_URL,
        'linkedin': COLUMN_NAMES.LINKEDIN_URL,
        'sequence': COLUMN_NAMES.MESSAGE_SEQUENCE_SHEET
      };
      
      // Process each row
      for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const contactData = {};
        
        // Map CSV data to contact fields
        for (let j = 0; j < csvHeaders.length; j++) {
          const csvHeader = csvHeaders[j].toLowerCase().trim();
          const mappedField = fieldMappings[csvHeader];
          
          if (mappedField && row[j]) {
            contactData[mappedField] = row[j].trim();
          }
        }
        
        // Validate required fields
        if (!contactData[COLUMN_NAMES.EMAIL]) {
          results.errors.push(`Row ${i + 1}: Missing email`);
          results.skipped++;
          continue;
        }
        
        // Check if contact exists
        const existing = this.getContactByEmail(contactData[COLUMN_NAMES.EMAIL]);
        if (existing) {
          results.skipped++;
          continue;
        }
        
        // Add contact
        const addResult = this.addContact({
          email: contactData[COLUMN_NAMES.EMAIL],
          firstName: contactData[COLUMN_NAMES.FIRST_NAME] || '',
          lastName: contactData[COLUMN_NAMES.LAST_NAME] || '',
          company: contactData[COLUMN_NAMES.COMPANY] || '',
          title: contactData[COLUMN_NAMES.TITLE] || '',
          linkedinUrl: contactData[COLUMN_NAMES.LINKEDIN_URL] || '',
          sequenceSheet: contactData[COLUMN_NAMES.MESSAGE_SEQUENCE_SHEET] || 'Default'
        });
        
        if (addResult.success) {
          results.imported++;
        } else {
          results.errors.push(`Row ${i + 1}: ${addResult.error}`);
        }
      }
      
      console.log(`✅ Import complete: ${results.imported} imported, ${results.skipped} skipped`);
      return results;
      
    } catch (error) {
      Services.logError('Data.importContactsFromCSV', error);
      results.success = false;
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Export contacts to CSV
   */
  exportContactsToCSV: function(filters = {}) {
    try {
      const contacts = this.getFilteredContacts(filters);
      
      // Build CSV headers
      const headers = [
        'Email',
        'First Name',
        'Last Name',
        'Company',
        'Title',
        'LinkedIn URL',
        'Sequence',
        'Campaign Start Date',
        'Paused',
        'Replied to Email',
        'Replied to LinkedIn',
        'Reply Date'
      ];
      
      // Build CSV rows
      const rows = [headers];
      
      for (const contact of contacts) {
        rows.push([
          contact.email,
          contact.firstName,
          contact.lastName,
          contact.company,
          contact.title,
          contact.linkedinUrl,
          contact.sequenceSheet,
          contact.campaignStartDate || '',
          contact.paused ? 'Yes' : 'No',
          contact.repliedToEmail ? 'Yes' : 'No',
          contact.repliedToLinkedIn ? 'Yes' : 'No',
          contact.replyDate || ''
        ]);
      }
      
      // Convert to CSV string
      const csvContent = rows.map(row => 
        row.map(cell => `"${(cell || '').toString().replace(/"/g, '""')}"`).join(',')
      ).join('\n');
      
      console.log(`📤 Exported ${contacts.length} contacts to CSV`);
      return csvContent;
      
    } catch (error) {
      Services.logError('Data.exportContactsToCSV', error);
      return null;
    }
  },
  
  /**
   * Get filtered contacts
   */
  getFilteredContacts: function(filters = {}) {
    let contacts = this.getAllContacts();
    
    // Apply filters
    if (filters.active !== undefined) {
      contacts = contacts.filter(c => 
        filters.active ? (!c.paused && !c.repliedToEmail && !c.repliedToLinkedIn) : 
                        (c.paused || c.repliedToEmail || c.repliedToLinkedIn)
      );
    }
    
    if (filters.sequence) {
      contacts = contacts.filter(c => c.sequenceSheet === filters.sequence);
    }
    
    if (filters.hasLinkedIn !== undefined) {
      contacts = contacts.filter(c => 
        filters.hasLinkedIn ? !!c.linkedinUrl : !c.linkedinUrl
      );
    }
    
    if (filters.campaignStarted !== undefined) {
      contacts = contacts.filter(c => 
        filters.campaignStarted ? !!c.campaignStartDate : !c.campaignStartDate
      );
    }
    
    return contacts;
  },
  
  /**
   * Backup spreadsheet data
   */
  backupData: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const backupName = `${ss.getName()}_Backup_${Services.formatDate(new Date(), 'yyyy-MM-dd_HHmm')}`;
      
      // Create copy
      const backup = ss.copy(backupName);
      
      console.log(`💾 Backup created: ${backupName}`);
      return { 
        success: true, 
        backupId: backup.getId(),
        backupName: backupName 
      };
      
    } catch (error) {
      Services.logError('Data.backupData', error);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Clean duplicate contacts
   */
  cleanDuplicates: function() {
    console.log("🧹 Cleaning duplicate contacts...");
    
    const results = {
      duplicatesFound: 0,
      duplicatesRemoved: 0,
      errors: []
    };
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      const emailIndex = headers.indexOf(COLUMN_NAMES.EMAIL);
      
      const seenEmails = new Set();
      const rowsToDelete = [];
      
      // Find duplicates
      for (let i = 1; i < data.length; i++) {
        const email = data[i][emailIndex];
        if (!email) continue;
        
        if (seenEmails.has(email.toLowerCase())) {
          results.duplicatesFound++;
          rowsToDelete.push(i + 1); // Sheet rows are 1-indexed
        } else {
          seenEmails.add(email.toLowerCase());
        }
      }
      
      // Delete duplicates (in reverse order to maintain indices)
      for (let i = rowsToDelete.length - 1; i >= 0; i--) {
        contactSheet.deleteRow(rowsToDelete[i]);
        results.duplicatesRemoved++;
      }
      
      console.log(`✅ Removed ${results.duplicatesRemoved} duplicate contacts`);
      return results;
      
    } catch (error) {
      Services.logError('Data.cleanDuplicates', error);
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Validate all contact data
   */
  validateAllContacts: function() {
    console.log("🔍 Validating all contact data...");
    
    const results = {
      total: 0,
      valid: 0,
      issues: []
    };
    
    try {
      const contacts = this.getAllContacts();
      results.total = contacts.length;
      
      for (const contact of contacts) {
        const issues = [];
        
        // Validate email
        if (!Services.validateEmail(contact.email)) {
          issues.push(`Invalid email: ${contact.email}`);
        }
        
        // Validate LinkedIn URL
        if (contact.linkedinUrl && !Services.validateLinkedInUrl(contact.linkedinUrl)) {
          issues.push(`Invalid LinkedIn URL: ${contact.linkedinUrl}`);
        }
        
        // Validate sequence
        if (contact.sequenceSheet) {
          const sequenceConfig = Services.getContactSequenceConfig(contact.sequenceSheet);
          if (!sequenceConfig || !sequenceConfig.isValid()) {
            issues.push(`Invalid sequence: ${contact.sequenceSheet}`);
          }
        }
        
        if (issues.length === 0) {
          results.valid++;
        } else {
          results.issues.push({
            contact: contact.displayName(),
            issues: issues
          });
        }
      }
      
      console.log(`✅ Validation complete: ${results.valid}/${results.total} contacts valid`);
      return results;
      
    } catch (error) {
      Services.logError('Data.validateAllContacts', error);
      return results;
    }
  }
};

// Legacy function mappings
function getAllContacts() {
  return Data.getAllContacts();
}

function getContactByEmail(email) {
  return Data.getContactByEmail(email);
}

function addNewContact(contactData) {
  return Data.addContact(contactData);
}

function importContactsCSV(csvData) {
  return Data.importContactsFromCSV(csvData);
}