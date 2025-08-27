// ======================
// DOGNOSIS OUTREACH AUTOMATION - DATA MIGRATOR
// Migrate existing data to optimized structure
// ======================

const DataMigrator = {
  /**
   * Migrate ContactList data to optimized structure
   */
  migrateContactList: function(sourceSheetName = "ContactList", targetSheetName = "ContactList") {
    console.log(`🔄 Migrating ContactList data from ${sourceSheetName} to ${targetSheetName}...`);
    
    const results = {
      success: true,
      migrated: 0,
      errors: [],
      backup: null
    };
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const sourceSheet = ss.getSheetByName(sourceSheetName);
      const targetSheet = ss.getSheetByName(targetSheetName);
      
      if (!sourceSheet) {
        results.success = false;
        results.errors.push(`Source sheet "${sourceSheetName}" not found`);
        return results;
      }
      
      if (!targetSheet) {
        results.success = false;
        results.errors.push(`Target sheet "${targetSheetName}" not found`);
        return results;
      }
      
      // Backup source data
      results.backup = this.backupSheet(sourceSheet);
      
      // Get source data
      const sourceData = sourceSheet.getDataRange().getValues();
      const sourceHeaders = sourceData[0];
      
      // Get target headers
      const targetHeaders = targetSheet.getRange(1, 1, 1, targetSheet.getLastColumn()).getValues()[0];
      
      // Create column mapping
      const columnMapping = this.createContactListMapping(sourceHeaders, targetHeaders);
      
      // Migrate data row by row
      const migratedRows = [];
      
      for (let i = 1; i < sourceData.length; i++) {
        const sourceRow = sourceData[i];
        const targetRow = this.mapContactRow(sourceRow, columnMapping, sourceHeaders, targetHeaders);
        
        if (targetRow) {
          migratedRows.push(targetRow);
          results.migrated++;
        }
      }
      
      // Write migrated data to target sheet
      if (migratedRows.length > 0) {
        const targetRange = targetSheet.getRange(2, 1, migratedRows.length, targetHeaders.length);
        targetRange.setValues(migratedRows);
      }
      
      console.log(`✅ Migrated ${results.migrated} contact records`);
      return results;
      
    } catch (error) {
      Services.logError('DataMigrator.migrateContactList', error);
      results.success = false;
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Migrate sequence data to optimized structure
   */
  migrateSequence: function(sourceSheetName, targetSheetName = null) {
    targetSheetName = targetSheetName || sourceSheetName;
    console.log(`🔄 Migrating sequence data from ${sourceSheetName} to ${targetSheetName}...`);
    
    const results = {
      success: true,
      migrated: 0,
      errors: [],
      backup: null
    };
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const sourceSheet = ss.getSheetByName(sourceSheetName);
      const targetSheet = ss.getSheetByName(targetSheetName);
      
      if (!sourceSheet || !targetSheet) {
        results.success = false;
        results.errors.push(`Sheet "${sourceSheetName}" or "${targetSheetName}" not found`);
        return results;
      }
      
      // Backup source data
      results.backup = this.backupSheet(sourceSheet);
      
      // Get source data
      const sourceData = sourceSheet.getDataRange().getValues();
      const sourceHeaders = sourceData[0];
      
      // Get target headers
      const targetHeaders = targetSheet.getRange(1, 1, 1, targetSheet.getLastColumn()).getValues()[0];
      
      // Create column mapping
      const columnMapping = this.createSequenceMapping(sourceHeaders, targetHeaders);
      
      // Migrate data row by row
      const migratedRows = [];
      
      for (let i = 1; i < sourceData.length; i++) {
        const sourceRow = sourceData[i];
        const targetRow = this.mapSequenceRow(sourceRow, columnMapping, sourceHeaders, targetHeaders);
        
        if (targetRow) {
          migratedRows.push(targetRow);
          results.migrated++;
        }
      }
      
      // Write migrated data to target sheet
      if (migratedRows.length > 0) {
        const targetRange = targetSheet.getRange(2, 1, migratedRows.length, targetHeaders.length);
        targetRange.setValues(migratedRows);
      }
      
      console.log(`✅ Migrated ${results.migrated} sequence steps`);
      return results;
      
    } catch (error) {
      Services.logError('DataMigrator.migrateSequence', error);
      results.success = false;
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Create column mapping for ContactList
   */
  createContactListMapping: function(sourceHeaders, targetHeaders) {
    const mapping = {};
    
    // Direct mappings
    const directMappings = {
      "First Name": "First Name",
      "Last Name": "Last Name", 
      "Title": "Title",
      "Company": "Company",
      "Email": "Email",
      "Linkedin Url": "LinkedIn URL",
      "LinkedIn URL": "LinkedIn URL",
      "Message Sequence Sheet": "Sequence",
      "Campaign Start Date": "Campaign Start Date",
      "Paused?": "Status", // Will need conversion
      "Replied to Email?": "Reply Channel", // Will need conversion
      "Replied to LinkedIn?": "Reply Channel", // Will need conversion
      "Reply Date": "Reply Date",
      "Notes": "Notes"
    };
    
    // Create mapping
    for (const [sourceCol, targetCol] of Object.entries(directMappings)) {
      const sourceIndex = sourceHeaders.indexOf(sourceCol);
      const targetIndex = targetHeaders.indexOf(targetCol);
      
      if (sourceIndex !== -1 && targetIndex !== -1) {
        mapping[targetCol] = {
          sourceIndex: sourceIndex,
          targetIndex: targetIndex,
          transform: this.getTransformFunction(sourceCol, targetCol)
        };
      }
    }
    
    return mapping;
  },
  
  /**
   * Create column mapping for sequences
   */
  createSequenceMapping: function(sourceHeaders, targetHeaders) {
    const mapping = {};
    
    // Direct mappings for sequences
    const directMappings = {
      "Day": "Day",
      "Step ": "Action Type", // Note: original has trailing space
      "Step": "Action Type",
      "Email new or reply to previous email": "Email Type",
      "Subject": "Subject",
      "Body": "Message Content",
      "Description": "Description",
      "Talking Point": "Notes"
    };
    
    // Create mapping
    for (const [sourceCol, targetCol] of Object.entries(directMappings)) {
      const sourceIndex = sourceHeaders.indexOf(sourceCol);
      const targetIndex = targetHeaders.indexOf(targetCol);
      
      if (sourceIndex !== -1 && targetIndex !== -1) {
        mapping[targetCol] = {
          sourceIndex: sourceIndex,
          targetIndex: targetIndex,
          transform: this.getSequenceTransformFunction(sourceCol, targetCol)
        };
      }
    }
    
    return mapping;
  },
  
  /**
   * Map a contact row from source to target format
   */
  mapContactRow: function(sourceRow, columnMapping, sourceHeaders, targetHeaders) {
    const targetRow = new Array(targetHeaders.length).fill("");
    
    try {
      // Apply direct mappings
      for (const [targetCol, mapping] of Object.entries(columnMapping)) {
        const sourceValue = sourceRow[mapping.sourceIndex];
        const transformedValue = mapping.transform ? mapping.transform(sourceValue, sourceRow, sourceHeaders) : sourceValue;
        targetRow[mapping.targetIndex] = transformedValue || "";
      }
      
      // Set default values for new columns
      this.setContactDefaults(targetRow, targetHeaders);
      
      return targetRow;
      
    } catch (error) {
      Services.logError('DataMigrator.mapContactRow', error);
      return null;
    }
  },
  
  /**
   * Map a sequence row from source to target format
   */
  mapSequenceRow: function(sourceRow, columnMapping, sourceHeaders, targetHeaders) {
    const targetRow = new Array(targetHeaders.length).fill("");
    
    try {
      // Apply direct mappings
      for (const [targetCol, mapping] of Object.entries(columnMapping)) {
        const sourceValue = sourceRow[mapping.sourceIndex];
        const transformedValue = mapping.transform ? mapping.transform(sourceValue, sourceRow, sourceHeaders) : sourceValue;
        targetRow[mapping.targetIndex] = transformedValue || "";
      }
      
      return targetRow;
      
    } catch (error) {
      Services.logError('DataMigrator.mapSequenceRow', error);
      return null;
    }
  },
  
  /**
   * Get transform function for contact fields
   */
  getTransformFunction: function(sourceCol, targetCol) {
    switch (targetCol) {
      case "Status":
        return (value) => {
          if (!value) return "Active";
          const val = value.toString().toLowerCase();
          if (val === "yes" || val === "true" || val === "paused") return "Paused";
          return "Active";
        };
        
      case "LinkedIn URL":
        return (value) => {
          if (!value) return "";
          const url = value.toString().trim();
          if (url && !url.startsWith("http")) {
            return `https://www.${url}`;
          }
          return url;
        };
        
      case "Reply Channel":
        return (value, sourceRow, sourceHeaders) => {
          // Check both email and LinkedIn reply columns
          const repliedEmailIndex = sourceHeaders.indexOf("Replied to Email?");
          const repliedLinkedInIndex = sourceHeaders.indexOf("Replied to LinkedIn?");
          
          const repliedEmail = repliedEmailIndex !== -1 && sourceRow[repliedEmailIndex] === "Yes";
          const repliedLinkedIn = repliedLinkedInIndex !== -1 && sourceRow[repliedLinkedInIndex] === "Yes";
          
          if (repliedEmail && repliedLinkedIn) return "Both";
          if (repliedEmail) return "Email";
          if (repliedLinkedIn) return "LinkedIn";
          return "";
        };
        
      case "Priority":
        return () => "Medium"; // Default priority
        
      default:
        return null; // No transformation
    }
  },
  
  /**
   * Get transform function for sequence fields
   */
  getSequenceTransformFunction: function(sourceCol, targetCol) {
    switch (targetCol) {
      case "Action Type":
        return (value) => {
          if (!value) return "";
          const val = value.toString().toLowerCase().trim();
          
          if (val.includes("email")) return "Email";
          if (val.includes("li connect") || val.includes("linkedin connect") || val.includes("connect")) return "LinkedIn_Connect";
          if (val.includes("li message") || val.includes("linkedin message") || val.includes("message") || val.includes("dm")) return "LinkedIn_Message";
          
          return val; // Return as-is if no match
        };
        
      case "Email Type":
        return (value) => {
          if (!value) return "";
          const val = value.toString().toLowerCase();
          if (val.includes("reply")) return "Reply";
          if (val.includes("new")) return "Initial";
          return "Initial"; // Default
        };
        
      case "Message Content":
        return (value) => {
          if (!value) return "";
          // Standardize placeholders
          return value.toString()
            .replace(/\{\{FirstName\}\}/g, "{First Name}")
            .replace(/\{\{First Name\}\}/g, "{First Name}")
            .replace(/\{\{Name\}\}/g, "{First Name}")
            .replace(/\{\{contact\.first_name\}\}/g, "{First Name}")
            .replace(/\{\{LastName\}\}/g, "{Last Name}")
            .replace(/\{\{Last Name\}\}/g, "{Last Name}")
            .replace(/\{\{Company\}\}/g, "{Company}")
            .replace(/\{\{FullName\}\}/g, "{First Name} {Last Name}")
            .replace(/\{\{Full Name\}\}/g, "{First Name} {Last Name}");
        };
        
      default:
        return null; // No transformation
    }
  },
  
  /**
   * Set default values for new contact columns
   */
  setContactDefaults: function(targetRow, targetHeaders) {
    const defaults = {
      "Status": "Active",
      "Priority": "Medium",
      "Source": "Migration",
      "Last Contact Date": "",
      "Response Type": "",
      "Next Action": "",
      "Created Date": new Date(),
      "Last Modified": new Date()
    };
    
    for (const [column, defaultValue] of Object.entries(defaults)) {
      const index = targetHeaders.indexOf(column);
      if (index !== -1 && !targetRow[index]) {
        targetRow[index] = defaultValue;
      }
    }
  },
  
  /**
   * Backup a sheet
   */
  backupSheet: function(sheet) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const backupName = `${sheet.getName()}_Backup_${Services.formatDate(new Date(), 'yyyy-MM-dd_HHmm')}`;
      
      // Copy the sheet
      const backup = sheet.copyTo(ss);
      backup.setName(backupName);
      
      console.log(`📋 Created backup: ${backupName}`);
      return backupName;
      
    } catch (error) {
      Services.logError('DataMigrator.backupSheet', error);
      return null;
    }
  },
  
  /**
   * Run complete migration
   */
  runCompleteMigration: function() {
    console.log("🚀 Starting complete data migration...");
    
    const results = {
      success: true,
      contactList: null,
      sequences: [],
      errors: []
    };
    
    try {
      // Migrate ContactList
      const contactResult = this.migrateContactList();
      results.contactList = contactResult;
      if (!contactResult.success) {
        results.errors.push(`ContactList: ${contactResult.errors.join(", ")}`);
      }
      
      // Find and migrate all sequence sheets
      const sequenceSheets = SpreadsheetOptimizer.getSequenceSheetNames();
      for (const sheetName of sequenceSheets) {
        const sequenceResult = this.migrateSequence(sheetName);
        results.sequences.push(sequenceResult);
        if (!sequenceResult.success) {
          results.errors.push(`${sheetName}: ${sequenceResult.errors.join(", ")}`);
        }
      }
      
      results.success = results.errors.length === 0;
      
      if (results.success) {
        console.log("✅ Complete migration successful!");
        console.log(`   📋 ContactList: ${contactResult.migrated} records`);
        console.log(`   📋 Sequences: ${results.sequences.length} sheets migrated`);
      } else {
        console.log("⚠️ Migration completed with errors:");
        results.errors.forEach(error => console.log(`   ❌ ${error}`));
      }
      
      return results;
      
    } catch (error) {
      Services.logError('DataMigrator.runCompleteMigration', error);
      results.success = false;
      results.errors.push(error.toString());
      return results;
    }
  }
};

// Legacy function support
function migrateContactListData() {
  return DataMigrator.migrateContactList();
}

function migrateSequenceData(sheetName) {
  return DataMigrator.migrateSequence(sheetName);
}

function runCompleteMigration() {
  return DataMigrator.runCompleteMigration();
}