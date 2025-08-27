// ======================
// DOGNOSIS OUTREACH AUTOMATION - EMAIL DOMAIN
// Gmail integration and email automation
// ======================

const Email = {
  /**
   * Send email for specific day in sequence
   */
  sendForDay: function(contact, day) {
    try {
      // Get sequence content for this day
      const content = Services.getSequenceContent(
        contact.sequenceSheet, 
        day, 
        contact.firstName, 
        contact.lastName, 
        contact.company
      );
      
      if (!content || !content.subject || !content.body) {
        return { success: false, error: `No email content for day ${day}` };
      }
      
      // Check Gmail quota
      const quota = MailApp.getRemainingDailyQuota();
      if (quota < VALIDATION.MIN_GMAIL_QUOTA) {
        return { success: false, error: `Low Gmail quota: ${quota} remaining` };
      }
      
      // Validate email
      if (!Services.validateEmail(contact.email)) {
        return { success: false, error: `Invalid email: ${contact.email}` };
      }
      
      // Send email
      const emailResult = this.sendPersonalizedEmail(
        contact.email,
        content.subject,
        content.body,
        content.isReply
      );
      
      if (emailResult.success) {
        // Track email sent
        this.trackEmailSent(contact, day);
        
        console.log(`📧 Email sent to ${contact.displayName()} (Day ${day})`);
        return { success: true };
      } else {
        return { success: false, error: emailResult.error };
      }
      
    } catch (error) {
      Services.logError('Email.sendForDay', error, { contact: contact.email, day });
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Send personalized email with reply handling and Gmail signature
   */
  sendPersonalizedEmail: function(toEmail, subject, body, isReply = false) {
    try {
      // Get Gmail signature from constants
      const signature = this.getGmailSignature();
      
      // Add signature to body if not already present
      const bodyWithSignature = this.addSignatureToBody(body, signature, isReply);
      
      if (isReply) {
        // For replies, search for existing thread and reply
        try {
          const threads = GmailApp.search(`to:${toEmail} subject:"${subject.replace('Re: ', '')}"`);
          if (threads.length > 0) {
            const thread = threads[0];
            thread.reply(bodyWithSignature);
            console.log(`📧 Replied to existing thread for ${toEmail} with signature`);
          } else {
            // No thread found, send as new email with Re: prefix
            GmailApp.sendEmail(toEmail, `Re: ${subject}`, bodyWithSignature);
            console.log(`📧 Sent new email with Re: prefix for ${toEmail} with signature`);
          }
        } catch (e) {
          console.log(`Reply search failed, sending as new email: ${e.toString()}`);
          GmailApp.sendEmail(toEmail, `Re: ${subject}`, bodyWithSignature);
        }
      } else {
        // For new emails, add signature and send
        GmailApp.sendEmail(toEmail, subject, bodyWithSignature);
        console.log(`📧 Sent new email to ${toEmail} with signature`);
      }
      
      return { success: true };
      
    } catch (error) {
      console.log(`❌ GmailApp failed, trying MailApp fallback: ${error.toString()}`);
      // Fallback to MailApp if GmailApp fails
      try {
        const signature = this.getGmailSignature();
        const bodyWithSignature = this.addSignatureToBody(body, signature, isReply);
        
        if (isReply) {
          const options = {
            replyTo: Session.getActiveUser().getEmail(),
            name: "Dognosis Outreach"
          };
          MailApp.sendEmail(toEmail, `Re: ${subject}`, bodyWithSignature, options);
        } else {
          MailApp.sendEmail(toEmail, subject, bodyWithSignature);
        }
        return { success: true };
      } catch (fallbackError) {
        return { success: false, error: fallbackError.toString() };
      }
    }
  },
  
  /**
   * Get Gmail signature
   */
  getGmailSignature: function() {
    // Your actual Gmail signature
    return `\n--\nBest,\nAmir Alpert\nBusiness Development | Dognosis.tech`;
  },
  
  /**
   * Add signature to email body if not already present
   */
  addSignatureToBody: function(body, signature, isReply = false) {
    if (!body || !signature) return body;
    
    // Check if signature is already present
    if (body.includes('Amir Alpert') || body.includes('Dognosis.tech')) {
      return body; // Signature already present
    }
    
    // For replies, use a simpler signature
    if (isReply) {
      const replySignature = `\n--\nBest,\nAmir Alpert`;
      return body + replySignature;
    }
    
    // For new emails, use full signature
    return body + signature;
  },
  
  /**
   * Batch send emails for multiple contacts
   */
  batchSendEmails: function(emailTasks) {
    const results = {
      success: true,
      successCount: 0,
      errors: [],
      quota: MailApp.getRemainingDailyQuota()
    };
    
    try {
      // Check batch size limit
      if (emailTasks.length > CAMPAIGN_LIMITS.MAX_BATCH_SIZE) {
        results.errors.push(`Batch too large: ${emailTasks.length} (max ${CAMPAIGN_LIMITS.MAX_BATCH_SIZE})`);
        results.success = false;
        return results;
      }
      
      // Process each email
      for (let i = 0; i < emailTasks.length; i++) {
        const task = emailTasks[i];
        
        // Check quota before each email
        if (MailApp.getRemainingDailyQuota() < VALIDATION.MIN_GMAIL_QUOTA) {
          results.errors.push("Gmail quota exhausted");
          results.success = false;
          break;
        }
        
        const emailResult = this.sendForDay(task.contact, task.day);
        if (emailResult.success) {
          results.successCount++;
        } else {
          results.errors.push(`${task.contact.displayName()}: ${emailResult.error}`);
        }
        
        // Human-like delay between each email (random 1-3 minutes)
        if (i < emailTasks.length - 1) { // Don't delay after last email
          const randomDelay = Math.random() * (180000 - 60000) + 60000; // 1-3 minutes (60-180 seconds)
          console.log(`⏳ Human-like delay: ${Math.round(randomDelay/1000)} seconds...`);
          Utilities.sleep(randomDelay);
        }
        
        // Additional longer delay every 10 emails (extended break)
        if (results.successCount > 0 && results.successCount % 10 === 0) {
          console.log(`📧 Batch progress: ${results.successCount}/${emailTasks.length} emails sent`);
          console.log(`⏳ Extended break: 5-10 minutes...`);
          const extendedDelay = Math.random() * (600000 - 300000) + 300000; // 5-10 minutes
          Utilities.sleep(extendedDelay);
        }
      }
      
      results.success = results.errors.length === 0;
      return results;
      
    } catch (error) {
      results.success = false;
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Track email sent in spreadsheet
   */
  trackEmailSent: function(contact, day) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      
      // Find tracking column
      const trackingColumn = CONSTANTS_UTILS.getEmailSentColumn(day);
      const columnIndex = headers.indexOf(trackingColumn);
      
      if (columnIndex !== -1) {
        const timestamp = new Date();
        contactSheet.getRange(contact.rowIndex + 1, columnIndex + 1).setValue(timestamp);
      }
      
    } catch (error) {
      Services.logError('Email.trackEmailSent', error, { contact: contact.email, day });
    }
  },
  
  /**
   * Get email statistics
   */
  getEmailStats: function(days = 30) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - days);
      
      let totalSent = 0;
      let todaySent = 0;
      const dailyStats = {};
      
      // Scan all email tracking columns
      for (let j = 0; j < headers.length; j++) {
        const header = headers[j];
        if (header.includes("Email Sent")) {
          
          for (let i = 1; i < data.length; i++) {
            const cellValue = data[i][j];
            if (cellValue && cellValue instanceof Date) {
              if (cellValue >= cutoffDate) {
                totalSent++;
                
                const dateStr = Services.formatDate(cellValue, 'yyyy-MM-dd');
                dailyStats[dateStr] = (dailyStats[dateStr] || 0) + 1;
                
                // Count today's emails
                const today = Services.formatDate(new Date(), 'yyyy-MM-dd');
                if (dateStr === today) {
                  todaySent++;
                }
              }
            }
          }
        }
      }
      
      const averagePerDay = totalSent / days;
      
      return {
        totalSent,
        todaySent,
        averagePerDay: Math.round(averagePerDay * 10) / 10,
        dailyStats,
        quotaRemaining: MailApp.getRemainingDailyQuota(),
        periodDays: days
      };
      
    } catch (error) {
      Services.logError('Email.getEmailStats', error, { days });
      return {
        totalSent: 0,
        todaySent: 0,
        averagePerDay: 0,
        dailyStats: {},
        quotaRemaining: 0,
        error: error.toString()
      };
    }
  },
  
  /**
   * Check for email replies and update contact status
   */
  checkForReplies: function() {
    console.log("📬 Checking for email replies...");
    
    const results = {
      newReplies: 0,
      totalChecked: 0,
      errors: []
    };
    
    try {
      // Get recent emails (last 7 days)
      const threads = GmailApp.search('is:unread', 0, 50);
      results.totalChecked = threads.length;
      
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      for (const thread of threads) {
        const messages = thread.getMessages();
        for (const message of messages) {
          if (message.isUnread()) {
            const fromEmail = message.getFrom();
            
            // Find contact by email
            for (let i = 1; i < data.length; i++) {
              const row = data[i];
              const contact = Services.createContactFromRow(row, headers, i);
              
              if (fromEmail.includes(contact.email)) {
                // Mark as replied
                this.markContactAsReplied(contact, message.getDate());
                results.newReplies++;
                
                console.log(`📨 Reply detected from ${contact.displayName()}`);
                break;
              }
            }
            
            // Mark as read
            message.markRead();
          }
        }
      }
      
      if (results.newReplies > 0) {
        console.log(`✅ Processed ${results.newReplies} new replies`);
      }
      
      return results;
      
    } catch (error) {
      Services.logError('Email.checkForReplies', error);
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Mark contact as replied in spreadsheet
   */
  markContactAsReplied: function(contact, replyDate) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      
      // Update reply channel
      const replyChannelIndex = headers.indexOf(COLUMN_NAMES.REPLY_CHANNEL);
      if (replyChannelIndex !== -1) {
        contactSheet.getRange(contact.rowIndex + 1, replyChannelIndex + 1).setValue("Email");
      }
      
      // Update reply date
      const replyDateIndex = headers.indexOf(COLUMN_NAMES.REPLY_DATE);
      if (replyDateIndex !== -1) {
        contactSheet.getRange(contact.rowIndex + 1, replyDateIndex + 1).setValue(replyDate);
      }
      
      // Update status to Replied
      const statusIndex = headers.indexOf(COLUMN_NAMES.STATUS);
      if (statusIndex !== -1) {
        contactSheet.getRange(contact.rowIndex + 1, statusIndex + 1).setValue("Replied");
      }
      
    } catch (error) {
      Services.logError('Email.markContactAsReplied', error, { contact: contact.email });
    }
  },
  
  /**
   * Test email integration
   */
  testConnection: function() {
    try {
      const quota = MailApp.getRemainingDailyQuota();
      if (quota < 1) {
        return { success: false, error: "No Gmail quota remaining" };
      }
      
      // Send test email to self
      const testEmail = Session.getActiveUser().getEmail();
      MailApp.sendEmail(
        testEmail,
        "Dognosis Email Test",
        "This is a test email from Dognosis Email domain. Integration is working!"
      );
      
      return { 
        success: true, 
        quota: quota,
        testEmail: testEmail 
      };
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Get contacts ready for email today
   */
  getContactsReadyForEmail: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      const readyContacts = [];
      const today = new Date();
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        const contact = Services.createContactFromRow(row, headers, i);
        
        // Skip if paused, replied, or invalid
        if (contact.paused || contact.repliedToEmail || !contact.isValid()) {
          continue;
        }
        
        // Calculate days since campaign start
        const daysSinceStart = Services.getDaysSinceCampaignStart(contact);
        if (daysSinceStart < 0) continue; // No campaign start date
        
        // Check if there's an email for this day
        const sequenceConfig = Services.getContactSequenceConfig(contact.sequenceSheet);
        if (sequenceConfig && sequenceConfig.emailDays.includes(daysSinceStart + 1)) {
          
          // Check if email already sent for this day
          const trackingColumn = CONSTANTS_UTILS.getEmailSentColumn(daysSinceStart + 1);
          const trackingIndex = headers.indexOf(trackingColumn);
          
          if (trackingIndex === -1 || !row[trackingIndex]) {
            readyContacts.push({
              contact: contact,
              day: daysSinceStart + 1,
              daysSinceStart: daysSinceStart
            });
          }
        }
      }
      
      return readyContacts;
      
    } catch (error) {
      Services.logError('Email.getContactsReadyForEmail', error);
      return [];
    }
  }
};

// Top-level wrapper functions for Apps Script dropdown visibility
function sendForDay(contact, day) {
  return Email.sendForDay(contact, day);
}

function sendPersonalizedEmail(toEmail, subject, body, isReply = false) {
  return Email.sendPersonalizedEmail(toEmail, subject, body, isReply);
}

function getContactsReadyForEmail() {
  return Email.getContactsReadyForEmail();
}

function trackEmailSent(contact, day) {
  return Email.trackEmailSent(contact, day);
}

function testEmailConnection() {
  return Email.testConnection();
}

function checkEmailReplies() {
  return Email.checkForReplies();
}

function getEmailStats() {
  return Email.getEmailStats();
}

// Legacy function mappings for backward compatibility
function sendSequenceEmail(contact, day) {
  return Email.sendForDay(contact, day);
}

function sendBatchEmails(emailTasks) {
  return Email.batchSendEmails(emailTasks);
}