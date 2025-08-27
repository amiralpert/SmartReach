// ======================
// DOGNOSIS OUTREACH AUTOMATION - AUTOFIX DOMAIN
// Self-healing system for automatic issue resolution
// ======================

const AutoFix = {
  /**
   * Main self-diagnosis and repair function
   */
  selfDiagnoseAndRepair: function() {
    console.log("🔧 AUTO-FIX: Starting self-diagnosis and repair...");
    
    const fixes = {
      attempted: 0,
      successful: 0,
      failed: 0,
      issues: []
    };
    
    try {
      // Run all diagnostic checks
      const diagnostics = [
        this.checkAndFixColumnMismatches(),
        this.checkAndFixMissingColumns(),
        this.checkAndFixInvalidData(),
        this.checkAndFixPhantomBusterConfig(),
        this.checkAndFixTriggers(),
        this.checkAndFixSequenceSheets(),
        this.checkAndFixDuplicates(),
        this.checkAndFixPermissions()
      ];
      
      // Process results
      for (const result of diagnostics) {
        fixes.attempted++;
        if (result.success) {
          fixes.successful++;
          if (result.fixed > 0) {
            console.log(`✅ Fixed: ${result.message}`);
          }
        } else {
          fixes.failed++;
          fixes.issues.push(result.error || result.message);
        }
      }
      
      // Final report
      console.log("\n" + "=".repeat(50));
      console.log("🔧 AUTO-FIX COMPLETE");
      console.log(`✅ Successful fixes: ${fixes.successful}/${fixes.attempted}`);
      if (fixes.failed > 0) {
        console.log(`❌ Failed fixes: ${fixes.failed}`);
        fixes.issues.forEach(issue => console.log(`   • ${issue}`));
      }
      console.log("=".repeat(50));
      
      return fixes;
      
    } catch (error) {
      Services.logError('AutoFix.selfDiagnoseAndRepair', error);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Check and fix column name mismatches
   */
  checkAndFixColumnMismatches: function() {
    console.log("🔍 Checking column name consistency...");
    
    const result = {
      success: true,
      fixed: 0,
      message: "Column names"
    };
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      
      // Define correct column mappings
      const columnFixes = {
        "Person Linkedin Url": COLUMN_NAMES.LINKEDIN_URL,
        "LinkedIn URL": COLUMN_NAMES.LINKEDIN_URL,
        "Email Address": COLUMN_NAMES.EMAIL,
        "First": COLUMN_NAMES.FIRST_NAME,
        "Last": COLUMN_NAMES.LAST_NAME,
        "Company Name": COLUMN_NAMES.COMPANY,
        "Job Title": COLUMN_NAMES.TITLE,
        "Sequence": COLUMN_NAMES.MESSAGE_SEQUENCE_SHEET,
        "Campaign Start": COLUMN_NAMES.CAMPAIGN_START_DATE,
        "Is Paused": COLUMN_NAMES.PAUSED,
        "Email Reply": COLUMN_NAMES.REPLIED_TO_EMAIL,
        "LinkedIn Reply": COLUMN_NAMES.REPLIED_TO_LINKEDIN
      };
      
      // Fix mismatched columns
      for (let i = 0; i < headers.length; i++) {
        const currentHeader = headers[i];
        const correctHeader = columnFixes[currentHeader];
        
        if (correctHeader && currentHeader !== correctHeader) {
          contactSheet.getRange(1, i + 1).setValue(correctHeader);
          result.fixed++;
          console.log(`   📝 Fixed: "${currentHeader}" → "${correctHeader}"`);
        }
      }
      
      result.message = `Column names (${result.fixed} fixed)`;
      return result;
      
    } catch (error) {
      result.success = false;
      result.error = error.toString();
      return result;
    }
  },
  
  /**
   * Check and create missing required columns
   */
  checkAndFixMissingColumns: function() {
    console.log("🔍 Checking for missing columns...");
    
    const result = {
      success: true,
      fixed: 0,
      message: "Missing columns"
    };
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      let headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      
      // Add missing required columns
      for (const requiredCol of VALIDATION.REQUIRED_COLUMNS) {
        if (!headers.includes(requiredCol)) {
          const newColIndex = headers.length + 1;
          contactSheet.getRange(1, newColIndex).setValue(requiredCol);
          headers.push(requiredCol);
          result.fixed++;
          console.log(`   ➕ Added missing column: "${requiredCol}"`);
        }
      }
      
      // Create tracking columns for all sequences
      const sequenceSheets = Services.getAllSequenceSheets();
      for (const sheetName of sequenceSheets) {
        const trackingColumns = Services.getSequenceTrackingColumns(sheetName);
        const createResult = Services.createMissingTrackingColumns(trackingColumns);
        if (createResult.success && createResult.columnsCreated > 0) {
          result.fixed += createResult.columnsCreated;
        }
      }
      
      result.message = `Missing columns (${result.fixed} added)`;
      return result;
      
    } catch (error) {
      result.success = false;
      result.error = error.toString();
      return result;
    }
  },
  
  /**
   * Check and fix invalid data
   */
  checkAndFixInvalidData: function() {
    console.log("🔍 Checking for invalid data...");
    
    const result = {
      success: true,
      fixed: 0,
      message: "Invalid data"
    };
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      // Get column indices
      const emailIndex = headers.indexOf(COLUMN_NAMES.EMAIL);
      const linkedinIndex = headers.indexOf(COLUMN_NAMES.LINKEDIN_URL);
      const pausedIndex = headers.indexOf(COLUMN_NAMES.PAUSED);
      const repliedEmailIndex = headers.indexOf(COLUMN_NAMES.REPLIED_TO_EMAIL);
      const repliedLinkedInIndex = headers.indexOf(COLUMN_NAMES.REPLIED_TO_LINKEDIN);
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        let rowUpdated = false;
        
        // Fix email format
        if (emailIndex !== -1 && row[emailIndex]) {
          const email = row[emailIndex].toString().trim().toLowerCase();
          if (email !== row[emailIndex]) {
            contactSheet.getRange(i + 1, emailIndex + 1).setValue(email);
            rowUpdated = true;
          }
        }
        
        // Fix LinkedIn URL format
        if (linkedinIndex !== -1 && row[linkedinIndex]) {
          const url = row[linkedinIndex].toString().trim();
          if (url && !url.startsWith("http")) {
            const fixedUrl = `https://www.linkedin.com/in/${url}`;
            contactSheet.getRange(i + 1, linkedinIndex + 1).setValue(fixedUrl);
            rowUpdated = true;
          }
        }
        
        // Fix Yes/No values
        const yesNoColumns = [
          { index: pausedIndex, name: COLUMN_NAMES.PAUSED },
          { index: repliedEmailIndex, name: COLUMN_NAMES.REPLIED_TO_EMAIL },
          { index: repliedLinkedInIndex, name: COLUMN_NAMES.REPLIED_TO_LINKEDIN }
        ];
        
        for (const col of yesNoColumns) {
          if (col.index !== -1 && row[col.index]) {
            const value = row[col.index].toString().toLowerCase();
            if (value === "true" || value === "1" || value === "yes") {
              contactSheet.getRange(i + 1, col.index + 1).setValue("Yes");
              rowUpdated = true;
            } else if (value === "false" || value === "0" || value === "no") {
              contactSheet.getRange(i + 1, col.index + 1).setValue("No");
              rowUpdated = true;
            }
          }
        }
        
        if (rowUpdated) result.fixed++;
      }
      
      result.message = `Invalid data (${result.fixed} rows fixed)`;
      return result;
      
    } catch (error) {
      result.success = false;
      result.error = error.toString();
      return result;
    }
  },
  
  /**
   * Check and fix PhantomBuster configuration
   */
  checkAndFixPhantomBusterConfig: function() {
    console.log("🔍 Checking PhantomBuster configuration...");
    
    const result = {
      success: true,
      fixed: 0,
      message: "PhantomBuster config"
    };
    
    try {
      const config = Services.getProperty('phantombuster_config');
      
      if (!config) {
        // Try to restore from backup
        const backup = Services.getProperty('phantombuster_config_backup');
        if (backup) {
          Services.setProperty('phantombuster_config', backup);
          result.fixed = 1;
          console.log("   ✅ Restored PhantomBuster config from backup");
        } else {
          result.message = "PhantomBuster config (needs manual setup)";
        }
      } else {
        // Validate existing config
        try {
          const parsedConfig = JSON.parse(config);
          const required = ['apiKey', 'networkBoosterId', 'messageSenderId', 'linkedinCookie'];
          let needsUpdate = false;
          
          for (const field of required) {
            if (!parsedConfig[field] || parsedConfig[field] === '') {
              needsUpdate = true;
              break;
            }
          }
          
          if (needsUpdate) {
            result.message = "PhantomBuster config (incomplete - needs manual update)";
          } else {
            // Create backup
            Services.setProperty('phantombuster_config_backup', config);
          }
        } catch (e) {
          result.message = "PhantomBuster config (invalid JSON)";
        }
      }
      
      return result;
      
    } catch (error) {
      result.success = false;
      result.error = error.toString();
      return result;
    }
  },
  
  /**
   * Check and fix automation triggers
   */
  checkAndFixTriggers: function() {
    console.log("🔍 Checking automation triggers...");
    
    const result = {
      success: true,
      fixed: 0,
      message: "Automation triggers"
    };
    
    try {
      const triggers = ScriptApp.getProjectTriggers();
      
      // Look for automation triggers
      const automationTrigger = triggers.find(t => 
        t.getHandlerFunction().includes('runDailyAutomation') ||
        t.getHandlerFunction().includes('runIntelligentAutomation')
      );
      
      if (!automationTrigger) {
        // Create default daily trigger
        ScriptApp.newTrigger('Orchestrator.runIntelligentAutomation')
          .timeBased()
          .atHour(9)
          .everyDays(1)
          .create();
        
        result.fixed = 1;
        console.log("   ✅ Created daily automation trigger (9 AM)");
      }
      
      // Remove duplicate triggers
      const handlerCounts = {};
      for (const trigger of triggers) {
        const handler = trigger.getHandlerFunction();
        handlerCounts[handler] = (handlerCounts[handler] || 0) + 1;
      }
      
      for (const trigger of triggers) {
        const handler = trigger.getHandlerFunction();
        if (handlerCounts[handler] > 1) {
          ScriptApp.deleteTrigger(trigger);
          handlerCounts[handler]--;
          result.fixed++;
          console.log(`   🗑️ Removed duplicate trigger: ${handler}`);
        }
      }
      
      result.message = `Automation triggers (${result.fixed} fixed)`;
      return result;
      
    } catch (error) {
      result.success = false;
      result.error = error.toString();
      return result;
    }
  },
  
  /**
   * Check and fix sequence sheets
   */
  checkAndFixSequenceSheets: function() {
    console.log("🔍 Checking sequence sheets...");
    
    const result = {
      success: true,
      fixed: 0,
      message: "Sequence sheets"
    };
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const sequenceSheets = Services.getAllSequenceSheets();
      
      for (const sheetName of sequenceSheets) {
        const sheet = ss.getSheetByName(sheetName);
        if (!sheet) continue;
        
        const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
        let sheetUpdated = false;
        
        // Ensure required sequence columns exist
        const requiredColumns = [
          SEQUENCE_COLUMNS.DAY,
          SEQUENCE_COLUMNS.SUBJECT,
          SEQUENCE_COLUMNS.BODY,
          SEQUENCE_COLUMNS.STEP
        ];
        
        for (const reqCol of requiredColumns) {
          if (!headers.includes(reqCol)) {
            const newColIndex = headers.length + 1;
            sheet.getRange(1, newColIndex).setValue(reqCol);
            headers.push(reqCol);
            sheetUpdated = true;
            console.log(`   ➕ Added column "${reqCol}" to ${sheetName}`);
          }
        }
        
        if (sheetUpdated) result.fixed++;
      }
      
      // Create default sequence if none exist
      if (sequenceSheets.length === 0) {
        this.createDefaultSequence();
        result.fixed++;
        console.log("   ✅ Created default sequence sheet");
      }
      
      result.message = `Sequence sheets (${result.fixed} fixed)`;
      return result;
      
    } catch (error) {
      result.success = false;
      result.error = error.toString();
      return result;
    }
  },
  
  /**
   * Check and fix duplicate contacts
   */
  checkAndFixDuplicates: function() {
    console.log("🔍 Checking for duplicate contacts...");
    
    const result = {
      success: true,
      fixed: 0,
      message: "Duplicate contacts"
    };
    
    try {
      const cleanResult = Data.cleanDuplicates();
      result.fixed = cleanResult.duplicatesRemoved;
      result.message = `Duplicate contacts (${result.fixed} removed)`;
      
      return result;
      
    } catch (error) {
      result.success = false;
      result.error = error.toString();
      return result;
    }
  },
  
  /**
   * Check and fix permissions
   */
  checkAndFixPermissions: function() {
    console.log("🔍 Checking permissions...");
    
    const result = {
      success: true,
      fixed: 0,
      message: "Permissions"
    };
    
    try {
      // Test critical permissions
      const permissionTests = [
        { service: 'Gmail', test: () => MailApp.getRemainingDailyQuota() },
        { service: 'Spreadsheet', test: () => SpreadsheetApp.getActiveSpreadsheet() },
        { service: 'Properties', test: () => PropertiesService.getScriptProperties().getProperty('test') },
        { service: 'UrlFetch', test: () => UrlFetchApp.getRequest('https://www.google.com') }
      ];
      
      const missingPermissions = [];
      
      for (const perm of permissionTests) {
        try {
          perm.test();
        } catch (e) {
          missingPermissions.push(perm.service);
        }
      }
      
      if (missingPermissions.length > 0) {
        result.message = `Permissions (${missingPermissions.join(', ')} need authorization)`;
        result.success = false;
      } else {
        result.message = "Permissions (all granted)";
      }
      
      return result;
      
    } catch (error) {
      result.success = false;
      result.error = error.toString();
      return result;
    }
  },
  
  /**
   * Create default sequence sheet
   */
  createDefaultSequence: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const defaultSheet = ss.insertSheet("Default");
      
      // Add headers
      const headers = [
        SEQUENCE_COLUMNS.DAY,
        SEQUENCE_COLUMNS.STEP,
        SEQUENCE_COLUMNS.SUBJECT,
        SEQUENCE_COLUMNS.BODY,
        SEQUENCE_COLUMNS.EMAIL_TYPE
      ];
      
      defaultSheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      
      // Add sample sequence
      const sampleData = [
        [1, "Email", "Introduction to {Company}", "Hi {First Name},\n\nI noticed your work at {Company}...", "Initial"],
        [3, "LinkedIn Connect", "", "Hi {First Name}, I'd love to connect!", ""],
        [5, "Email", "Following up", "Hi {First Name},\n\nJust wanted to follow up...", "Follow-up"],
        [7, "LinkedIn Message", "", "Hi {First Name}, thanks for connecting!", ""]
      ];
      
      defaultSheet.getRange(2, 1, sampleData.length, headers.length).setValues(sampleData);
      
      console.log("✅ Created default sequence sheet");
      
    } catch (error) {
      Services.logError('AutoFix.createDefaultSequence', error);
    }
  },
  
  /**
   * Detect and fix column mismatches (called from Main.js)
   */
  detectAndFixColumnMismatches: function() {
    return this.checkAndFixColumnMismatches();
  }
};

// Top-level wrapper functions for Apps Script dropdown visibility
function selfDiagnoseAndRepair() {
  return AutoFix.selfDiagnoseAndRepair();
}

function checkAndFixColumnMismatches() {
  return AutoFix.checkAndFixColumnMismatches();
}

function checkAndFixMissingColumns() {
  return AutoFix.checkAndFixMissingColumns();
}

function checkAndFixInvalidData() {
  return AutoFix.checkAndFixInvalidData();
}

function checkAndFixPhantomBusterConfig() {
  return AutoFix.checkAndFixPhantomBusterConfig();
}

function checkAndFixTriggers() {
  return AutoFix.checkAndFixTriggers();
}

function checkAndFixSequenceSheets() {
  return AutoFix.checkAndFixSequenceSheets();
}

function checkAndFixDuplicates() {
  return AutoFix.checkAndFixDuplicates();
}

function checkAndFixPermissions() {
  return AutoFix.checkAndFixPermissions();
}

function createDefaultSequence() {
  return AutoFix.createDefaultSequence();
}

function detectAndFixColumnMismatches() {
  return AutoFix.detectAndFixColumnMismatches();
}

// Legacy function support for backward compatibility
function runAutoFix() {
  return AutoFix.selfDiagnoseAndRepair();
}

function fixColumnMismatches() {
  return AutoFix.detectAndFixColumnMismatches();
}