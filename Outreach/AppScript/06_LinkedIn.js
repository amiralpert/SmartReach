// ======================
// DOGNOSIS OUTREACH AUTOMATION - LINKEDIN DOMAIN
// PhantomBuster integration with Google Sheets
// ======================

const LinkedIn = {
  /**
   * Test PhantomBuster API connection
   */
  testConnection: function() {
    try {
      const config = Services.getProperty('phantombuster_config');
      if (!config) {
        return { success: false, error: "PhantomBuster not configured" };
      }
      
      const parsedConfig = JSON.parse(config);
      
      // Test API key with agent status check
      const url = `${PHANTOMBUSTER.API_BASE_URL}/agent/${parsedConfig.networkBoosterId}`;
      const response = UrlFetchApp.fetch(url, {
        method: 'GET',
        headers: {
          'X-Phantombuster-Key': parsedConfig.apiKey,
          'Accept': 'application/json'
        },
        muteHttpExceptions: true
      });
      
      if (response.getResponseCode() === 200) {
        return { success: true, message: "PhantomBuster API connected" };
      } else {
        return { success: false, error: `API error: ${response.getResponseCode()}` };
      }
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Process all LinkedIn connections for today
   */
  processConnectionsForToday: function(connectionTasks) {
    console.log(`🤝 Processing ${connectionTasks.length} LinkedIn connections...`);
    
    const results = {
      success: true,
      successCount: 0,
      failedContacts: [],
      errors: []
    };
    
    try {
      // Prepare Google Sheet data
      const sheetUpdateResult = this.updatePhantomBusterSheet(connectionTasks, 'connect');
      if (!sheetUpdateResult.success) {
        throw new Error(`Failed to update sheet: ${sheetUpdateResult.error}`);
      }
      
      // Launch PhantomBuster agent
      const launchResult = this.launchPhantomBusterAgent('connect');
      if (!launchResult.success) {
        throw new Error(`Failed to launch agent: ${launchResult.error}`);
      }
      
      // Poll for completion
      const pollResult = this.pollPhantomBusterStatus(launchResult.containerId);
      
      if (pollResult.status === 'finished') {
        results.successCount = connectionTasks.length;
        console.log(`✅ Successfully processed ${results.successCount} connections`);
      } else if (pollResult.status === 'failed' || pollResult.status === 'timeout') {
        // Retry once after delay
        console.log(`⚠️ First attempt failed, retrying in 5 minutes...`);
        Utilities.sleep(300000); // 5 minutes
        
        const retryLaunch = this.launchPhantomBusterAgent('connect');
        if (retryLaunch.success) {
          const retryPoll = this.pollPhantomBusterStatus(retryLaunch.containerId);
          if (retryPoll.status === 'finished') {
            results.successCount = connectionTasks.length;
            console.log(`✅ Retry successful - processed ${results.successCount} connections`);
          } else {
            // Mark all as failed
            this.markContactsAsFailed(connectionTasks, 'connect', pollResult.error);
            results.failedContacts = connectionTasks;
            results.errors.push(`Connection batch failed after retry: ${pollResult.error}`);
            
            // Send failure notification
            this.sendFailureNotification('connect', connectionTasks, pollResult.error);
          }
        }
      }
      
    } catch (error) {
      results.success = false;
      results.errors.push(error.toString());
      results.failedContacts = connectionTasks;
      this.markContactsAsFailed(connectionTasks, 'connect', error.toString());
      this.sendFailureNotification('connect', connectionTasks, error.toString());
    }
    
    return results;
  },
  
  /**
   * Process all LinkedIn messages for today
   */
  processMessagesForToday: function(messageTasks) {
    console.log(`💬 Processing ${messageTasks.length} LinkedIn messages...`);
    
    const results = {
      success: true,
      successCount: 0,
      failedContacts: [],
      errors: []
    };
    
    try {
      // Prepare Google Sheet data
      const sheetUpdateResult = this.updatePhantomBusterSheet(messageTasks, 'message');
      if (!sheetUpdateResult.success) {
        throw new Error(`Failed to update sheet: ${sheetUpdateResult.error}`);
      }
      
      // Launch PhantomBuster agent
      const launchResult = this.launchPhantomBusterAgent('message');
      if (!launchResult.success) {
        throw new Error(`Failed to launch agent: ${launchResult.error}`);
      }
      
      // Poll for completion
      const pollResult = this.pollPhantomBusterStatus(launchResult.containerId);
      
      if (pollResult.status === 'finished') {
        results.successCount = messageTasks.length;
        console.log(`✅ Successfully processed ${results.successCount} messages`);
      } else if (pollResult.status === 'failed' || pollResult.status === 'timeout') {
        // Retry once after delay
        console.log(`⚠️ First attempt failed, retrying in 5 minutes...`);
        Utilities.sleep(300000); // 5 minutes
        
        const retryLaunch = this.launchPhantomBusterAgent('message');
        if (retryLaunch.success) {
          const retryPoll = this.pollPhantomBusterStatus(retryLaunch.containerId);
          if (retryPoll.status === 'finished') {
            results.successCount = messageTasks.length;
            console.log(`✅ Retry successful - processed ${results.successCount} messages`);
          } else {
            // Mark all as failed
            this.markContactsAsFailed(messageTasks, 'message', pollResult.error);
            results.failedContacts = messageTasks;
            results.errors.push(`Message batch failed after retry: ${pollResult.error}`);
            
            // Send failure notification
            this.sendFailureNotification('message', messageTasks, pollResult.error);
          }
        }
      }
      
    } catch (error) {
      results.success = false;
      results.errors.push(error.toString());
      results.failedContacts = messageTasks;
      this.markContactsAsFailed(messageTasks, 'message', error.toString());
      this.sendFailureNotification('message', messageTasks, error.toString());
    }
    
    return results;
  },
  
  /**
   * Update the PhantomBuster Google Sheet with LinkedIn URLs and messages
   */
  updatePhantomBusterSheet: function(tasks, taskType) {
    try {
      console.log(`📝 Updating PhantomBuster sheet with ${tasks.length} ${taskType} tasks...`);
      
      // Open the PhantomBuster sheet
      const sheetId = '1jvJSIDBTZ_zwwy-myGdRPfDKXnsnastwwU9FgSfoHWU';
      const sheet = SpreadsheetApp.openById(sheetId).getActiveSheet();
      
      // Clear existing content (keep headers)
      const lastRow = sheet.getLastRow();
      if (lastRow > 1) {
        sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).clearContent();
      }
      
      // Prepare data array
      const data = [];
      for (const task of tasks) {
        const cleanedUrl = Services.cleanLinkedInUrl(task.contact.linkedinUrl);
        
        // Get message content for this specific day and sequence
        const content = Services.getSequenceContent(
          task.contact.sequenceSheet,
          task.day,
          task.contact.firstName,
          task.contact.lastName,
          task.contact.company
        );
        
        const message = content ? (content.linkedinMessage || content.body) : '';
        
        data.push([cleanedUrl, message]);
      }
      
      // Write data to sheet
      if (data.length > 0) {
        sheet.getRange(2, 1, data.length, 2).setValues(data);
        console.log(`✅ Sheet updated with ${data.length} rows`);
      }
      
      // Force sheet to save
      SpreadsheetApp.flush();
      
      return { success: true, rowsUpdated: data.length };
      
    } catch (error) {
      console.log(`❌ Sheet update failed: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Launch PhantomBuster agent
   */
  launchPhantomBusterAgent: function(taskType) {
    try {
      const config = JSON.parse(Services.getProperty('phantombuster_config'));
      
      // Determine which agent to use
      const agentId = taskType === 'connect' ? 
        config.networkBoosterId : 
        config.messageSenderId;
      
      console.log(`🚀 Launching ${taskType} agent (${agentId})...`);
      
      const url = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/launch`;
      const payload = {}; // Agent ID is in the URL path
      
      const response = UrlFetchApp.fetch(url, {
        method: 'POST',
        headers: {
          'X-Phantombuster-Key': config.apiKey,
          'Content-Type': 'application/json'
        },
        payload: JSON.stringify(payload),
        muteHttpExceptions: true
      });
      
      const responseCode = response.getResponseCode();
      const result = JSON.parse(response.getContentText());
      
      // PhantomBuster returns {status: "success", data: {containerId: "..."}}
      if (responseCode === 200 && result.status === 'success' && result.data && result.data.containerId) {
        console.log(`✅ Agent launched with container ID: ${result.data.containerId}`);
        return { 
          success: true, 
          containerId: result.data.containerId
        };
      } else if (responseCode === 200 && result.containerId) {
        // Alternative response format
        console.log(`✅ Agent launched with container ID: ${result.containerId}`);
        return { 
          success: true, 
          containerId: result.containerId
        };
      } else {
        console.log(`❌ Agent launch failed: ${JSON.stringify(result)}`);
        return { 
          success: false, 
          error: result.message || result.error || 'Unknown error',
          details: result
        };
      }
      
    } catch (error) {
      console.log(`❌ Launch error: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Poll PhantomBuster container status
   */
  pollPhantomBusterStatus: function(containerId) {
    try {
      const config = JSON.parse(Services.getProperty('phantombuster_config'));
      const maxWaitTime = 600000; // 10 minutes
      const pollInterval = 30000; // 30 seconds
      const startTime = new Date().getTime();
      
      console.log(`⏳ Polling container ${containerId} status...`);
      
      while (true) {
        // PhantomBuster doesn't have direct container endpoints - check via agent output
        const config = JSON.parse(Services.getProperty('phantombuster_config'));
        // Try to determine correct agent by checking container history of both agents
        let agentId = config.networkBoosterId; // Default to connection agent
        const url = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/output`;
        const response = UrlFetchApp.fetch(url, {
          method: 'GET',
          headers: {
            'X-Phantombuster-Key': config.apiKey,
            'Accept': 'application/json'
          },
          muteHttpExceptions: true
        });
        
        if (response.getResponseCode() === 200) {
          const result = JSON.parse(response.getContentText());
          
          // Handle agent output response structure
          if (result.status === 'success' && result.data) {
            const data = result.data;
            
            // Check if the container we're looking for matches
            if (data.containerId !== containerId) {
              console.log(`   ⚠️ Container mismatch. Expected: ${containerId}, Current: ${data.containerId}`);
              // Agent might be running a different container or finished
            }
            
            const agentStatus = data.agentStatus || 'unknown';
            const containerStatus = data.containerStatus || 'unknown';
            
            console.log(`   📊 Agent Status: ${agentStatus}`);
            console.log(`   📊 Container Status: ${containerStatus}`);
            
            if (data.progress && data.progress.progress !== null) {
              console.log(`   📊 Progress: ${data.progress.progress}%`);
            }
            
            // Check if container finished
            if (agentStatus === 'not running' && containerStatus === 'not running') {
              // Need to check containers history for final status
              const containersUrl = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/containers`;
              const containersResponse = UrlFetchApp.fetch(containersUrl, {
                method: 'GET',
                headers: {
                  'X-Phantombuster-Key': config.apiKey,
                  'Accept': 'application/json'
                },
                muteHttpExceptions: true
              });
              
              if (containersResponse.getResponseCode() === 200) {
                const containersResult = JSON.parse(containersResponse.getContentText());
                if (containersResult.status === 'success' && containersResult.data) {
                  const container = containersResult.data.find(c => c.id === containerId);
                  if (container) {
                    console.log(`   📊 Container Exit Status: ${container.lastEndStatus}`);
                    if (container.lastEndStatus === 'success') {
                      return { status: 'finished', result: container };
                    } else if (container.lastEndStatus === 'error' || container.lastEndStatus === 'failed') {
                      return { 
                        status: 'failed', 
                        error: `Container failed with status: ${container.lastEndStatus}`,
                        result: container 
                      };
                    }
                  }
                }
              }
              
              return { status: 'finished', result: data };
            } else if (agentStatus === 'running') {
              // Still running, continue polling
              console.log('   ⏳ Agent still running...');
            }
          }
          
          // Check timeout
          if (new Date().getTime() - startTime > maxWaitTime) {
            return { status: 'timeout', error: 'Polling timeout after 10 minutes' };
          }
          
          // Still running, wait and try again
          Utilities.sleep(pollInterval);
          
        } else {
          return { 
            status: 'error', 
            error: `API error: ${response.getResponseCode()}`
          };
        }
      }
      
    } catch (error) {
      console.log(`❌ Polling error: ${error.toString()}`);
      return { status: 'error', error: error.toString() };
    }
  },
  
  /**
   * Mark contacts as failed in spreadsheet
   */
  markContactsAsFailed: function(tasks, taskType, errorMessage) {
    try {
      console.log(`📝 Marking ${tasks.length} contacts as failed...`);
      
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      
      // Find or create failure tracking columns
      let failedDateIndex = headers.indexOf("LinkedIn Failed Date");
      let failureReasonIndex = headers.indexOf("LinkedIn Failure Reason");
      
      if (failedDateIndex === -1) {
        failedDateIndex = headers.length;
        contactSheet.getRange(1, failedDateIndex + 1).setValue("LinkedIn Failed Date");
      }
      
      if (failureReasonIndex === -1) {
        failureReasonIndex = headers.length + (failedDateIndex === headers.length ? 1 : 0);
        contactSheet.getRange(1, failureReasonIndex + 1).setValue("LinkedIn Failure Reason");
      }
      
      // Update each failed contact
      for (const task of tasks) {
        const row = task.contact.rowIndex + 1;
        contactSheet.getRange(row, failedDateIndex + 1).setValue(new Date());
        contactSheet.getRange(row, failureReasonIndex + 1).setValue(
          `${taskType} - Day ${task.day}: ${errorMessage}`
        );
      }
      
      console.log(`✅ Marked ${tasks.length} contacts as failed`);
      
    } catch (error) {
      console.log(`❌ Error marking failures: ${error.toString()}`);
    }
  },
  
  /**
   * Send failure notification email
   */
  sendFailureNotification: function(taskType, failedTasks, errorMessage) {
    try {
      const adminEmail = Session.getActiveUser().getEmail();
      const subject = `🚨 LinkedIn Automation Failure - ${taskType}`;
      
      const contactDetails = failedTasks.map(task => 
        `- ${task.contact.firstName} ${task.contact.lastName} (${task.contact.email}) - Day ${task.day} ${taskType}`
      ).join('\n');
      
      const body = `
DOGNOSIS OUTREACH AUTOMATION ALERT

🚨 LinkedIn ${taskType} batch failed

Batch Type: ${taskType === 'connect' ? 'Connections' : 'Messages'}
Failed Contacts: ${failedTasks.length}
Error: ${errorMessage}
Retry: Attempted once, failed

Affected Contacts:
${contactDetails}

Action Required: Manual review in ContactList spreadsheet
Check "LinkedIn Failed Date" and "LinkedIn Failure Reason" columns

Time: ${new Date().toLocaleString()}

--
Best,
Amir Alpert
Business Development | Dognosis.tech
`;

      GmailApp.sendEmail(adminEmail, subject, body);
      console.log(`📧 Failure notification sent to ${adminEmail}`);
      
    } catch (error) {
      console.log(`❌ Failed to send notification: ${error.toString()}`);
    }
  },
  
  /**
   * Get LinkedIn statistics
   */
  getLinkedInStats: function(days = 30) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - days);
      
      let totalConnects = 0;
      let totalMessages = 0;
      let todayConnects = 0;
      let todayMessages = 0;
      let failedCount = 0;
      
      // Find failure column
      const failedDateIndex = headers.indexOf("LinkedIn Failed Date");
      
      // Scan all LinkedIn tracking columns
      for (let j = 0; j < headers.length; j++) {
        const header = headers[j];
        
        for (let i = 1; i < data.length; i++) {
          const cellValue = data[i][j];
          if (cellValue && cellValue instanceof Date && cellValue >= cutoffDate) {
            
            const isToday = Services.formatDate(cellValue, 'yyyy-MM-dd') === 
                           Services.formatDate(new Date(), 'yyyy-MM-dd');
            
            if (header.includes("LinkedIn Connect Sent")) {
              totalConnects++;
              if (isToday) todayConnects++;
            } else if (header.includes("LinkedIn DM Sent")) {
              totalMessages++;
              if (isToday) todayMessages++;
            }
          }
        }
      }
      
      // Count failures
      if (failedDateIndex !== -1) {
        for (let i = 1; i < data.length; i++) {
          if (data[i][failedDateIndex]) failedCount++;
        }
      }
      
      return {
        totalConnects,
        totalMessages,
        todayConnects,
        todayMessages,
        failedCount,
        averageConnectsPerDay: Math.round((totalConnects / days) * 10) / 10,
        averageMessagesPerDay: Math.round((totalMessages / days) * 10) / 10,
        periodDays: days
      };
      
    } catch (error) {
      Services.logError('LinkedIn.getLinkedInStats', error, { days });
      return {
        totalConnects: 0,
        totalMessages: 0,
        todayConnects: 0,
        todayMessages: 0,
        failedCount: 0,
        error: error.toString()
      };
    }
  }
};

// Simplified wrapper functions for Apps Script dropdown
function testLinkedInConnection() {
  const result = LinkedIn.testConnection();
  console.log('🔗 LinkedIn connection test result:', JSON.stringify(result, null, 2));
  return result;
}

function getLinkedInStats(days = 30) {
  return LinkedIn.getLinkedInStats(days);
}

// Legacy function mappings for backward compatibility
function sendConnection(contact, day) {
  console.log("⚠️ Legacy function called - use processDailyCampaigns() instead");
  return { success: false, error: "Use processDailyCampaigns() for automated LinkedIn" };
}

function sendMessage(contact, day) {
  console.log("⚠️ Legacy function called - use processDailyCampaigns() instead");
  return { success: false, error: "Use processDailyCampaigns() for automated LinkedIn" };
}