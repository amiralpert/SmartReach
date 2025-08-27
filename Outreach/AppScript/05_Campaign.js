// ======================
// DOGNOSIS OUTREACH AUTOMATION - CAMPAIGN DOMAIN
// Campaign management and contact lifecycle
// ======================

const Campaign = {
  /**
   * Start campaign for contact
   */
  startCampaign: function(contact) {
    try {
      // Validate contact
      if (!contact.isValid()) {
        return { success: false, error: "Invalid contact data" };
      }
      
      // Check if campaign already started
      if (contact.campaignStartDate) {
        return { success: false, error: "Campaign already started" };
      }
      
      // Validate sequence exists
      const sequenceConfig = Services.getContactSequenceConfig(contact.sequenceSheet);
      if (!sequenceConfig || !sequenceConfig.isValid()) {
        return { success: false, error: `Invalid sequence: ${contact.sequenceSheet}` };
      }
      
      // Set campaign start date
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      const startDateIndex = headers.indexOf(COLUMN_NAMES.CAMPAIGN_START_DATE);
      
      if (startDateIndex !== -1) {
        const today = new Date();
        contactSheet.getRange(contact.rowIndex + 1, startDateIndex + 1).setValue(today);
        
        console.log(`🚀 Campaign started for ${contact.displayName()}`);
        return { success: true, startDate: today };
      } else {
        return { success: false, error: "Campaign Start Date column not found" };
      }
      
    } catch (error) {
      Services.logError('Campaign.startCampaign', error, { contact: contact.email });
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Pause campaign for contact
   */
  pauseCampaign: function(contact, reason = null) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      const pausedIndex = headers.indexOf(COLUMN_NAMES.PAUSED);
      
      if (pausedIndex !== -1) {
        contactSheet.getRange(contact.rowIndex + 1, pausedIndex + 1).setValue("Yes");
        
        // Add pause reason if provided
        if (reason) {
          const notesIndex = headers.indexOf("Notes");
          if (notesIndex !== -1) {
            const existingNotes = contactSheet.getRange(contact.rowIndex + 1, notesIndex + 1).getValue();
            const newNotes = existingNotes ? 
              `${existingNotes} | Paused: ${reason} (${new Date().toLocaleDateString()})` :
              `Paused: ${reason} (${new Date().toLocaleDateString()})`;
            contactSheet.getRange(contact.rowIndex + 1, notesIndex + 1).setValue(newNotes);
          }
        }
        
        console.log(`⏸️ Campaign paused for ${contact.displayName()}`);
        return { success: true };
      } else {
        return { success: false, error: "Paused column not found" };
      }
      
    } catch (error) {
      Services.logError('Campaign.pauseCampaign', error, { contact: contact.email });
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Resume campaign for contact
   */
  resumeCampaign: function(contact) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      const pausedIndex = headers.indexOf(COLUMN_NAMES.PAUSED);
      
      if (pausedIndex !== -1) {
        contactSheet.getRange(contact.rowIndex + 1, pausedIndex + 1).setValue("No");
        
        console.log(`▶️ Campaign resumed for ${contact.displayName()}`);
        return { success: true };
      } else {
        return { success: false, error: "Paused column not found" };
      }
      
    } catch (error) {
      Services.logError('Campaign.resumeCampaign', error, { contact: contact.email });
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Get campaign status for contact
   */
  getCampaignStatus: function(contact) {
    try {
      const status = {
        active: false,
        paused: contact.paused,
        replied: contact.repliedToEmail || contact.repliedToLinkedIn,
        campaignStartDate: contact.campaignStartDate,
        daysSinceStart: -1,
        currentDay: 0,
        completedActions: [],
        upcomingActions: [],
        progress: 0
      };
      
      // Check if campaign started
      if (!contact.campaignStartDate) {
        status.message = "Campaign not started";
        return status;
      }
      
      // Calculate progress
      status.daysSinceStart = Services.getDaysSinceCampaignStart(contact);
      status.currentDay = status.daysSinceStart + 1;
      status.active = !status.paused && !status.replied;
      
      // Get sequence configuration
      const sequenceConfig = Services.getContactSequenceConfig(contact.sequenceSheet);
      if (!sequenceConfig) {
        status.message = "Invalid sequence configuration";
        return status;
      }
      
      // Check completed and upcoming actions
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      const row = contactSheet.getRange(contact.rowIndex + 1, 1, 1, headers.length).getValues()[0];
      
      // Check emails
      for (const day of sequenceConfig.emailDays) {
        const trackingColumn = CONSTANTS_UTILS.getEmailSentColumn(day);
        const columnIndex = headers.indexOf(trackingColumn);
        
        if (day <= status.currentDay) {
          if (columnIndex !== -1 && row[columnIndex]) {
            status.completedActions.push(`Email Day ${day}`);
          }
        } else {
          status.upcomingActions.push(`Email Day ${day}`);
        }
      }
      
      // Check LinkedIn connects
      for (const day of sequenceConfig.linkedinConnectDays) {
        const trackingColumn = CONSTANTS_UTILS.getLinkedInConnectColumn(day);
        const columnIndex = headers.indexOf(trackingColumn);
        
        if (day <= status.currentDay) {
          if (columnIndex !== -1 && row[columnIndex]) {
            status.completedActions.push(`LinkedIn Connect Day ${day}`);
          }
        } else {
          status.upcomingActions.push(`LinkedIn Connect Day ${day}`);
        }
      }
      
      // Check LinkedIn messages
      for (const day of sequenceConfig.linkedinMessageDays) {
        const trackingColumn = CONSTANTS_UTILS.getLinkedInMessageColumn(day);
        const columnIndex = headers.indexOf(trackingColumn);
        
        if (day <= status.currentDay) {
          if (columnIndex !== -1 && row[columnIndex]) {
            status.completedActions.push(`LinkedIn Message Day ${day}`);
          }
        } else {
          status.upcomingActions.push(`LinkedIn Message Day ${day}`);
        }
      }
      
      // Calculate progress
      const totalActions = sequenceConfig.emailDays.length + 
                          sequenceConfig.linkedinConnectDays.length + 
                          sequenceConfig.linkedinMessageDays.length;
      
      status.progress = totalActions > 0 ? 
        Math.round((status.completedActions.length / totalActions) * 100) : 0;
      
      return status;
      
    } catch (error) {
      Services.logError('Campaign.getCampaignStatus', error, { contact: contact.email });
      return { error: error.toString() };
    }
  },
  
  /**
   * Get all campaigns summary
   */
  getAllCampaignsSummary: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      const summary = {
        total: 0,
        active: 0,
        paused: 0,
        replied: 0,
        notStarted: 0,
        bySequence: {},
        byStatus: {
          active: [],
          paused: [],
          replied: [],
          notStarted: []
        }
      };
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        const contact = Services.createContactFromRow(row, headers, i);
        
        if (!contact.email) continue; // Skip empty rows
        
        summary.total++;
        
        // Categorize by status
        if (!contact.campaignStartDate) {
          summary.notStarted++;
          summary.byStatus.notStarted.push(contact.displayName());
        } else if (contact.repliedToEmail || contact.repliedToLinkedIn) {
          summary.replied++;
          summary.byStatus.replied.push(contact.displayName());
        } else if (contact.paused) {
          summary.paused++;
          summary.byStatus.paused.push(contact.displayName());
        } else {
          summary.active++;
          summary.byStatus.active.push(contact.displayName());
        }
        
        // Count by sequence
        if (contact.sequenceSheet) {
          summary.bySequence[contact.sequenceSheet] = 
            (summary.bySequence[contact.sequenceSheet] || 0) + 1;
        }
      }
      
      return summary;
      
    } catch (error) {
      Services.logError('Campaign.getAllCampaignsSummary', error);
      return { error: error.toString() };
    }
  },
  
  /**
   * Process daily campaigns
   */
  processDailyCampaigns: function() {
    console.log("📅 Processing daily campaigns...");
    
    const results = {
      processed: 0,
      emailsSent: 0,
      linkedinConnects: 0,
      linkedinMessages: 0,
      errors: []
    };
    
    try {
      // Get all active contacts with campaigns
      const activeContacts = this.getActiveCampaignContacts();
      console.log(`👥 Found ${activeContacts.length} active campaign contacts`);
      
      // Group by action type for today
      const todayActions = this.groupContactsByTodayActions(activeContacts);
      
      // Process emails
      if (todayActions.emails.length > 0) {
        console.log(`📧 Processing ${todayActions.emails.length} emails...`);
        const emailResult = Email.batchSendEmails(todayActions.emails);
        results.emailsSent = emailResult.successCount;
        results.errors.push(...emailResult.errors);
      }
      
      // Process LinkedIn connects (prioritize over messages)
      if (todayActions.linkedinConnects.length > 0) {
        console.log(`🤝 Processing ${todayActions.linkedinConnects.length} LinkedIn connects...`);
        const connectResult = LinkedIn.processConnectionsForToday(todayActions.linkedinConnects);
        results.linkedinConnects = connectResult.successCount;
        results.errors.push(...connectResult.errors);
      }
      
      // Process LinkedIn messages (after connections complete)
      if (todayActions.linkedinMessages.length > 0) {
        console.log(`💬 Processing ${todayActions.linkedinMessages.length} LinkedIn messages...`);
        const messageResult = LinkedIn.processMessagesForToday(todayActions.linkedinMessages);
        results.linkedinMessages = messageResult.successCount;
        results.errors.push(...messageResult.errors);
      }
      
      results.processed = activeContacts.length;
      
      console.log(`✅ Daily campaigns complete: ${results.emailsSent} emails, ${results.linkedinConnects} connects, ${results.linkedinMessages} messages`);
      
      return results;
      
    } catch (error) {
      Services.logError('Campaign.processDailyCampaigns', error);
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Get active campaign contacts
   */
  getActiveCampaignContacts: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      const activeContacts = [];
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        const contact = Services.createContactFromRow(row, headers, i);
        
        // Include if: has campaign, not paused, not replied, valid
        if (contact.campaignStartDate && 
            !contact.paused && 
            !contact.repliedToEmail && 
            !contact.repliedToLinkedIn &&
            contact.isValid()) {
          activeContacts.push(contact);
        }
      }
      
      return activeContacts;
      
    } catch (error) {
      Services.logError('Campaign.getActiveCampaignContacts', error);
      return [];
    }
  },
  
  /**
   * Group contacts by today's actions
   */
  groupContactsByTodayActions: function(contacts) {
    const todayActions = {
      emails: [],
      linkedinConnects: [],
      linkedinMessages: []
    };
    
    for (const contact of contacts) {
      const daysSinceStart = Services.getDaysSinceCampaignStart(contact);
      if (daysSinceStart < 0) continue;
      
      const currentDay = daysSinceStart + 1;
      const sequenceConfig = Services.getContactSequenceConfig(contact.sequenceSheet);
      
      if (!sequenceConfig) continue;
      
      // Check for email today
      if (sequenceConfig.emailDays.includes(currentDay)) {
        if (!this.isActionCompleted(contact, 'email', currentDay)) {
          todayActions.emails.push({ contact, day: currentDay });
        }
      }
      
      // Check for LinkedIn connect today
      if (sequenceConfig.linkedinConnectDays.includes(currentDay)) {
        if (!this.isActionCompleted(contact, 'connect', currentDay)) {
          todayActions.linkedinConnects.push({ contact, day: currentDay });
        }
      }
      
      // Check for LinkedIn message today
      if (sequenceConfig.linkedinMessageDays.includes(currentDay)) {
        if (!this.isActionCompleted(contact, 'message', currentDay)) {
          todayActions.linkedinMessages.push({ contact, day: currentDay });
        }
      }
    }
    
    return todayActions;
  },
  
  /**
   * Check if action is already completed
   */
  isActionCompleted: function(contact, actionType, day) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      const row = contactSheet.getRange(contact.rowIndex + 1, 1, 1, headers.length).getValues()[0];
      
      let trackingColumn;
      switch (actionType) {
        case 'email':
          trackingColumn = CONSTANTS_UTILS.getEmailSentColumn(day);
          break;
        case 'connect':
          trackingColumn = CONSTANTS_UTILS.getLinkedInConnectColumn(day);
          break;
        case 'message':
          trackingColumn = CONSTANTS_UTILS.getLinkedInMessageColumn(day);
          break;
      }
      
      const columnIndex = headers.indexOf(trackingColumn);
      return columnIndex !== -1 && row[columnIndex];
      
    } catch (error) {
      Services.logError('Campaign.isActionCompleted', error);
      return false;
    }
  },
  
  /**
   * Optimize campaign timing
   */
  optimizeCampaignTiming: function() {
    console.log("🧠 Optimizing campaign timing...");
    
    try {
      // Get response data
      const responseData = this.getResponseAnalytics();
      
      // Find best times
      const bestEmailTime = this.findBestTime(responseData.emailResponses);
      const bestLinkedInTime = this.findBestTime(responseData.linkedinResponses);
      
      // Update timing preferences
      Services.setProperty('optimal_email_hour', bestEmailTime.toString());
      Services.setProperty('optimal_linkedin_hour', bestLinkedInTime.toString());
      
      console.log(`📧 Optimal email time: ${bestEmailTime}:00`);
      console.log(`🤝 Optimal LinkedIn time: ${bestLinkedInTime}:00`);
      
      return {
        emailHour: bestEmailTime,
        linkedinHour: bestLinkedInTime
      };
      
    } catch (error) {
      Services.logError('Campaign.optimizeCampaignTiming', error);
      return { emailHour: 9, linkedinHour: 14 }; // Defaults
    }
  },
  
  /**
   * Get response analytics
   */
  getResponseAnalytics: function() {
    // Placeholder for response analytics
    return {
      emailResponses: [],
      linkedinResponses: []
    };
  },
  
  /**
   * Find best time from response data
   */
  findBestTime: function(responses) {
    // Simple implementation - can be enhanced with ML
    return 10; // Default to 10 AM
  }
};

// Top-level wrapper functions for Apps Script dropdown visibility
function startCampaign(contact) {
  return Campaign.startCampaign(contact);
}

function pauseCampaign(contact, reason = null) {
  return Campaign.pauseCampaign(contact, reason);
}

function resumeCampaign(contact) {
  return Campaign.resumeCampaign(contact);
}

function getCampaignStatus(contact) {
  return Campaign.getCampaignStatus(contact);
}

function getAllCampaignsSummary() {
  return Campaign.getAllCampaignsSummary();
}

function processDailyCampaigns() {
  return Campaign.processDailyCampaigns();
}

function getActiveCampaignContacts() {
  return Campaign.getActiveCampaignContacts();
}

function groupContactsByTodayActions(contacts) {
  return Campaign.groupContactsByTodayActions(contacts);
}

function isActionCompleted(contact, actionType, day) {
  return Campaign.isActionCompleted(contact, actionType, day);
}

function optimizeCampaignTiming() {
  return Campaign.optimizeCampaignTiming();
}

function getResponseAnalytics() {
  return Campaign.getResponseAnalytics();
}

function findBestTime(responses) {
  return Campaign.findBestTime(responses);
}

// Legacy function mappings for backward compatibility
function startContactCampaign(contact) {
  return Campaign.startCampaign(contact);
}

function pauseContactCampaign(contact, reason) {
  return Campaign.pauseCampaign(contact, reason);
}

function getContactCampaignStatus(contact) {
  return Campaign.getCampaignStatus(contact);
}

function runDailyCampaigns() {
  return Campaign.processDailyCampaigns();
}