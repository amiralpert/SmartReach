// ======================
// DOGNOSIS OUTREACH AUTOMATION - SERVICES DOMAIN
// Consolidated utility functions and services
// ======================

const Services = {
  // ====================
  // PROPERTY MANAGEMENT
  // ====================
  
  /**
   * Get property from script properties
   */
  getProperty: function(key) {
    try {
      return PropertiesService.getScriptProperties().getProperty(key);
    } catch (error) {
      console.log(`Error getting property ${key}: ${error.toString()}`);
      return null;
    }
  },
  
  /**
   * Set property in script properties
   */
  setProperty: function(key, value) {
    try {
      PropertiesService.getScriptProperties().setProperty(key, value);
      return { success: true };
    } catch (error) {
      console.log(`Error setting property ${key}: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },
  
  // ====================
  // CONTACT MANAGEMENT
  // ====================
  
  /**
   * Create contact object from spreadsheet row
   */
  createContactFromRow: function(row, headers, rowIndex) {
    const getColIndex = name => headers.indexOf(name);
    
    return {
      rowIndex: rowIndex,
      firstName: row[getColIndex(COLUMN_NAMES.FIRST_NAME)] || "",
      lastName: row[getColIndex(COLUMN_NAMES.LAST_NAME)] || "",
      title: row[getColIndex(COLUMN_NAMES.TITLE)] || "",
      company: row[getColIndex(COLUMN_NAMES.COMPANY)] || "",
      email: row[getColIndex(COLUMN_NAMES.EMAIL)] || "",
      linkedinUrl: row[getColIndex(COLUMN_NAMES.LINKEDIN_URL)] || "",
      sequenceSheet: row[getColIndex(COLUMN_NAMES.SEQUENCE)] || "",
      campaignStartDate: row[getColIndex(COLUMN_NAMES.CAMPAIGN_START_DATE)] || null,
      status: row[getColIndex(COLUMN_NAMES.STATUS)] || "Active",
      priority: row[getColIndex(COLUMN_NAMES.PRIORITY)] || "Medium",
      source: row[getColIndex(COLUMN_NAMES.SOURCE)] || "",
      lastContactDate: row[getColIndex(COLUMN_NAMES.LAST_CONTACT_DATE)] || null,
      replyDate: row[getColIndex(COLUMN_NAMES.REPLY_DATE)] || null,
      replyChannel: row[getColIndex(COLUMN_NAMES.REPLY_CHANNEL)] || "",
      responseType: row[getColIndex(COLUMN_NAMES.RESPONSE_TYPE)] || "",
      nextAction: row[getColIndex(COLUMN_NAMES.NEXT_ACTION)] || "",
      notes: row[getColIndex(COLUMN_NAMES.NOTES)] || "",
      
      // Computed properties for backward compatibility
      paused: (row[getColIndex(COLUMN_NAMES.STATUS)] || "").toString().toLowerCase() === "paused",
      repliedToEmail: (row[getColIndex(COLUMN_NAMES.REPLY_CHANNEL)] || "").toString().toLowerCase().includes("email"),
      repliedToLinkedIn: (row[getColIndex(COLUMN_NAMES.REPLY_CHANNEL)] || "").toString().toLowerCase().includes("linkedin"),
      
      // Utility methods
      fullName: function() { return `${this.firstName} ${this.lastName}`.trim(); },
      isValid: function() { return !!(this.email && this.firstName && this.sequenceSheet); },
      displayName: function() { return this.firstName || this.email || "Unknown Contact"; }
    };
  },
  
  // ====================
  // SEQUENCE MANAGEMENT
  // ====================
  
  /**
   * Get contact sequence configuration with caching
   */
  getContactSequenceConfig: function(sequenceSheetName) {
    try {
      // Check cache first
      const cacheKey = `sequence_${sequenceSheetName}`;
      const cached = this.getFromCache(cacheKey);
      if (cached) return cached;
      
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const sequenceSheet = ss.getSheetByName(sequenceSheetName);
      
      if (!sequenceSheet) {
        console.log(`❌ Sequence sheet "${sequenceSheetName}" not found`);
        return null;
      }
      
      const seqData = sequenceSheet.getDataRange().getValues();
      const seqHeaders = seqData[0];
      
      // Find columns using constants
      const dayIndex = this.findColumnIndex(seqHeaders, [SEQUENCE_COLUMNS.DAY]);
      const subjectIndex = this.findColumnIndex(seqHeaders, [SEQUENCE_COLUMNS.SUBJECT]);
      const bodyIndex = this.findColumnIndex(seqHeaders, [SEQUENCE_COLUMNS.MESSAGE_CONTENT]);
      const actionTypeIndex = this.findColumnIndex(seqHeaders, [SEQUENCE_COLUMNS.ACTION_TYPE]);
      const emailTypeIndex = this.findColumnIndex(seqHeaders, [SEQUENCE_COLUMNS.EMAIL_TYPE]);
      
      if (dayIndex === -1) {
        console.log(`❌ Day column not found in ${sequenceSheetName}`);
        return null;
      }
      
      // Parse sequence data
      const sequenceConfig = {
        name: sequenceSheetName,
        emailDays: [],
        linkedinConnectDays: [],
        linkedinMessageDays: [],
        sequenceData: {},
        maxDay: 0,
        
        // Utility methods
        getAllActionDays: function() {
          return [...new Set([
            ...this.emailDays,
            ...this.linkedinConnectDays,
            ...this.linkedinMessageDays
          ])].sort((a, b) => a - b);
        },
        
        hasDay: function(day) {
          return this.sequenceData.hasOwnProperty(day);
        },
        
        isValid: function() {
          return !!(
            this.name && 
            (this.emailDays.length > 0 || 
             this.linkedinConnectDays.length > 0 || 
             this.linkedinMessageDays.length > 0)
          );
        }
      };
      
      // Process each row
      for (let j = 1; j < seqData.length; j++) {
        const row = seqData[j];
        const dayValue = row[dayIndex];
        
        if (!dayValue) continue;
        
        const day = parseInt(dayValue);
        if (isNaN(day) || day < 1) continue;
        
        // Determine action type
        const actionTypeRaw = row[actionTypeIndex] ? row[actionTypeIndex].toString().toLowerCase() : '';
        const emailType = emailTypeIndex !== -1 ? row[emailTypeIndex] : null;
        const isReply = emailType && emailType.toString().toLowerCase() === 'reply';
        
        // Store row data
        sequenceConfig.sequenceData[day] = {
          day: day,
          subject: subjectIndex !== -1 ? row[subjectIndex] : null,
          body: bodyIndex !== -1 ? row[bodyIndex] : null,
          actionType: actionTypeIndex !== -1 ? row[actionTypeIndex] : null,
          emailType: emailType,
          isReply: isReply
        };
        
        // Categorize by action type using constants
        if (CONSTANTS_UTILS.stepMatchesActionType(actionTypeRaw, ACTION_TYPES.EMAIL)) {
          sequenceConfig.emailDays.push(day);
        } else if (CONSTANTS_UTILS.stepMatchesActionType(actionTypeRaw, ACTION_TYPES.LINKEDIN_CONNECT)) {
          sequenceConfig.linkedinConnectDays.push(day);
        } else if (CONSTANTS_UTILS.stepMatchesActionType(actionTypeRaw, ACTION_TYPES.LINKEDIN_MESSAGE)) {
          sequenceConfig.linkedinMessageDays.push(day);
        } else if (row[subjectIndex] && row[bodyIndex]) {
          // Default to email if has email content
          sequenceConfig.emailDays.push(day);
        }
        
        if (day > sequenceConfig.maxDay) {
          sequenceConfig.maxDay = day;
        }
      }
      
      // Sort day arrays
      sequenceConfig.emailDays.sort((a, b) => a - b);
      sequenceConfig.linkedinConnectDays.sort((a, b) => a - b);
      sequenceConfig.linkedinMessageDays.sort((a, b) => a - b);
      
      // Cache the result
      this.setInCache(cacheKey, sequenceConfig);
      
      return sequenceConfig;
      
    } catch (error) {
      console.log(`❌ Error reading sequence ${sequenceSheetName}: ${error.toString()}`);
      return null;
    }
  },
  
  /**
   * Get sequence content for specific day and contact
   */
  getSequenceContent: function(sequenceSheetName, day, firstName, lastName, company) {
    try {
      const config = this.getContactSequenceConfig(sequenceSheetName);
      if (!config || !config.sequenceData[day]) {
        return null;
      }
      
      const dayData = config.sequenceData[day];
      
      // Personalize content
      return {
        day: day,
        subject: this.personalizeContent(dayData.subject, firstName, lastName, company),
        body: this.personalizeContent(dayData.body, firstName, lastName, company),
        linkedinMessage: this.personalizeContent(dayData.body, firstName, lastName, company), // Use body for LinkedIn messages
        actionType: dayData.actionType,
        isReply: dayData.isReply
      };
      
    } catch (error) {
      console.log(`❌ Error getting content for Day ${day} from ${sequenceSheetName}: ${error.toString()}`);
      return null;
    }
  },
  
  /**
   * Get all sequence sheets in spreadsheet
   */
  getAllSequenceSheets: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const allSheets = ss.getSheets();
      
      return allSheets
        .filter(sheet => {
          const name = sheet.getName();
          if (name === 'ContactList' || name.startsWith('_')) return false;
          
          // Check if sheet has Day column
          try {
            const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
            return this.findColumnIndex(headers, [SEQUENCE_COLUMNS.DAY]) !== -1;
          } catch (e) {
            return false;
          }
        })
        .map(sheet => sheet.getName());
        
    } catch (error) {
      console.log(`❌ Error getting sequence sheets: ${error.toString()}`);
      return [];
    }
  },
  
  /**
   * Get tracking columns needed for a sequence
   */
  getSequenceTrackingColumns: function(sequenceSheetName) {
    const config = this.getContactSequenceConfig(sequenceSheetName);
    if (!config) return [];
    
    const columns = [];
    
    config.emailDays.forEach(day => {
      columns.push(CONSTANTS_UTILS.getEmailSentColumn(day));
    });
    
    config.linkedinConnectDays.forEach(day => {
      columns.push(CONSTANTS_UTILS.getLinkedInConnectColumn(day));
    });
    
    config.linkedinMessageDays.forEach(day => {
      columns.push(CONSTANTS_UTILS.getLinkedInMessageColumn(day));
    });
    
    return columns;
  },
  
  /**
   * Create missing tracking columns
   */
  createMissingTrackingColumns: function(requiredColumns) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      
      let columnsCreated = 0;
      
      for (const columnName of requiredColumns) {
        if (!headers.includes(columnName)) {
          const newColumnIndex = headers.length + 1;
          contactSheet.getRange(1, newColumnIndex).setValue(columnName);
          headers.push(columnName); // Update local headers array
          columnsCreated++;
        }
      }
      
      return { success: true, columnsCreated };
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Validate sequence sheet
   */
  validateSequenceSheet: function(sheetName) {
    const config = this.getContactSequenceConfig(sheetName);
    if (!config) {
      return { valid: false, issues: ["Failed to load sequence configuration"] };
    }
    
    const issues = [];
    
    if (config.emailDays.length === 0 && config.linkedinMessageDays.length === 0) {
      issues.push("No email or LinkedIn message content found");
    }
    
    if (config.maxDay > CAMPAIGN_LIMITS.MAX_SEQUENCE_LENGTH_DAYS) {
      issues.push(`Sequence too long (${config.maxDay} days)`);
    }
    
    return {
      valid: issues.length === 0,
      issues: issues,
      emailDays: config.emailDays.length,
      linkedinConnectDays: config.linkedinConnectDays.length,
      linkedinMessageDays: config.linkedinMessageDays.length
    };
  },
  
  // ====================
  // CONTENT PERSONALIZATION
  // ====================
  
  /**
   * Personalize content with contact information
   */
  personalizeContent: function(content, firstName, lastName, company) {
    if (!content) return content;
    
    let personalizedContent = content;
    
    console.log(`🔧 Personalizing content for: ${firstName} ${lastName} at ${company}`);
    console.log(`📝 Original content: ${content.substring(0, 100)}...`);
    
    // Direct placeholder replacement (more reliable)
    const replacements = [
      // First Name variations
      [/{First Name}/gi, firstName || ''],
      [/{FirstName}/gi, firstName || ''],
      [/{FIRST_NAME}/gi, firstName || ''],
      [/{first_name}/gi, firstName || ''],
      
      // Last Name variations  
      [/{Last Name}/gi, lastName || ''],
      [/{LastName}/gi, lastName || ''],
      [/{LAST_NAME}/gi, lastName || ''],
      [/{last_name}/gi, lastName || ''],
      
      // Company variations
      [/{Company}/gi, company || ''],
      [/{COMPANY}/gi, company || ''],
      [/{company}/gi, company || ''],
      
      // Full Name variations
      [/{Full Name}/gi, `${firstName} ${lastName}`.trim()],
      [/{FullName}/gi, `${firstName} ${lastName}`.trim()],
      [/{FULL_NAME}/gi, `${firstName} ${lastName}`.trim()]
    ];
    
    replacements.forEach(([pattern, replacement]) => {
      personalizedContent = personalizedContent.replace(pattern, replacement);
    });
    
    console.log(`✅ Personalized content: ${personalizedContent.substring(0, 100)}...`);
    return personalizedContent;
  },
  
  // ====================
  // VALIDATION UTILITIES
  // ====================
  
  /**
   * Validate email format
   */
  validateEmail: function(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  },
  
  /**
   * Clean and validate LinkedIn URL format
   */
  validateLinkedInUrl: function(url) {
    if (!url) return false;
    
    // Clean the URL first
    const cleanedUrl = this.cleanLinkedInUrl(url);
    
    // More flexible regex that allows numbers and longer usernames
    const linkedinRegex = /^https?:\/\/(www\.)?linkedin\.com\/in\/[\w\-0-9]+\/?$/;
    return linkedinRegex.test(cleanedUrl);
  },
  
  /**
   * Clean malformed LinkedIn URLs
   */
  cleanLinkedInUrl: function(url) {
    if (!url) return url;
    
    let cleaned = url.toString().trim();
    
    // Fix duplicate prefixes like "https://www.linkedin.com/in/www.linkedin.com/in/..."
    if (cleaned.includes('linkedin.com/in/') && cleaned.match(/linkedin\.com\/in\//g).length > 1) {
      // Extract just the username part after the last occurrence
      const lastPart = cleaned.substring(cleaned.lastIndexOf('/in/') + 4);
      cleaned = `https://www.linkedin.com/in/${lastPart}`;
    }
    
    // Remove trailing slashes and clean up
    cleaned = cleaned.replace(/\/+$/, '');
    
    // Ensure it starts with https://
    if (cleaned.startsWith('www.linkedin.com')) {
      cleaned = `https://${cleaned}`;
    } else if (cleaned.startsWith('linkedin.com')) {
      cleaned = `https://www.${cleaned}`;
    }
    
    return cleaned;
  },
  
  // ====================
  // CACHING UTILITIES
  // ====================
  
  /**
   * Get value from cache
   */
  getFromCache: function(key) {
    try {
      const cached = this.getProperty(`cache_${key}`);
      if (!cached) return null;
      
      const parsedCache = JSON.parse(cached);
      const now = new Date().getTime();
      
      if ((now - parsedCache.timestamp) < TIMING.SEQUENCE_CACHE_DURATION) {
        const data = parsedCache.data;
        
        // Restore methods for sequence config objects
        if (key.startsWith('sequence_') && data && data.name) {
          data.getAllActionDays = function() {
            return [...new Set([
              ...this.emailDays,
              ...this.linkedinConnectDays,
              ...this.linkedinMessageDays
            ])].sort((a, b) => a - b);
          };
          
          data.hasDay = function(day) {
            return this.sequenceData.hasOwnProperty(day);
          };
          
          data.isValid = function() {
            return !!(
              this.name && 
              (this.emailDays.length > 0 || 
               this.linkedinConnectDays.length > 0 || 
               this.linkedinMessageDays.length > 0)
            );
          };
        }
        
        return data;
      }
      
      // Cache expired
      return null;
      
    } catch (error) {
      return null;
    }
  },
  
  /**
   * Set value in cache
   */
  setInCache: function(key, data) {
    try {
      const cacheData = {
        timestamp: new Date().getTime(),
        data: data
      };
      
      this.setProperty(`cache_${key}`, JSON.stringify(cacheData));
    } catch (error) {
      console.log(`Cache set error: ${error.toString()}`);
    }
  },
  
  // ====================
  // HELPER UTILITIES
  // ====================
  
  /**
   * Find column index with multiple possible names
   */
  findColumnIndex: function(headers, possibleNames) {
    for (const name of possibleNames) {
      const index = headers.indexOf(name);
      if (index !== -1) return index;
    }
    return -1;
  },
  
  /**
   * Calculate days since campaign start
   */
  getDaysSinceCampaignStart: function(contact, referenceDate = null) {
    if (!contact.campaignStartDate) return -1;
    
    const startDate = new Date(contact.campaignStartDate);
    const compareDate = referenceDate ? new Date(referenceDate) : new Date();
    
    const timeDiff = compareDate.getTime() - startDate.getTime();
    return Math.floor(timeDiff / (1000 * 60 * 60 * 24));
  },
  
  /**
   * Format date for display
   */
  formatDate: function(date, format = 'MM/dd/yyyy') {
    try {
      return Utilities.formatDate(new Date(date), Session.getScriptTimeZone(), format);
    } catch (error) {
      return "Invalid Date";
    }
  },
  
  /**
   * Log error with context
   */
  logError: function(functionName, error, context = null) {
    const timestamp = new Date().toISOString();
    const errorMessage = typeof error === 'string' ? error : error.toString();
    const contextStr = context ? JSON.stringify(context) : 'No context';
    
    const logEntry = `[${timestamp}] ERROR in ${functionName}: ${errorMessage} | Context: ${contextStr}`;
    console.log(`🚨 ${logEntry}`);
    
    // Store recent errors
    try {
      const existingLogs = this.getProperty('error_logs') || '[]';
      const logs = JSON.parse(existingLogs);
      
      logs.push({
        timestamp: timestamp,
        function: functionName,
        error: errorMessage,
        context: context
      });
      
      // Keep only recent logs
      const recentLogs = logs.slice(-50);
      this.setProperty('error_logs', JSON.stringify(recentLogs));
    } catch (storageError) {
      console.log(`⚠️ Failed to store error log: ${storageError.toString()}`);
    }
  }
};

// Legacy function mappings
function personalizeSequenceContent(content, firstName, lastName, company) {
  return Services.personalizeContent(content, firstName, lastName, company);
}

function getSequenceContent(sequenceSheetName, day, firstName, lastName, company) {
  return Services.getSequenceContent(sequenceSheetName, day, firstName, lastName, company);
}

function getContactSequenceConfig(sequenceSheetName) {
  return Services.getContactSequenceConfig(sequenceSheetName);
}