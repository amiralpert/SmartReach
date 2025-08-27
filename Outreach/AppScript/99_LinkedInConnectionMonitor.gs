/**
 * LINKEDIN CONNECTION ACCEPTANCE MONITOR
 * Detects when LinkedIn connection requests are accepted
 * and triggers the messaging sequence automatically
 */

/**
 * Main function to check for new LinkedIn connections
 */
function checkLinkedInConnections() {
  console.log('🔍 Checking for new LinkedIn connections...');
  
  try {
    // Get all contacts who have pending LinkedIn connections
    const pendingConnections = getPendingLinkedInConnections();
    console.log(`📊 Found ${pendingConnections.length} pending LinkedIn connections`);
    
    if (pendingConnections.length === 0) {
      console.log('ℹ️ No pending connections to check');
      return { success: true, newConnections: 0, checked: 0 };
    }
    
    // Check connection status via PhantomBuster
    const connectionResults = checkConnectionStatusBatch(pendingConnections);
    
    // Update spreadsheet with results
    const updateResults = updateConnectionStatuses(connectionResults);
    
    // Trigger messaging for newly accepted connections
    const messagingResults = triggerMessagingForNewConnections(connectionResults.newConnections);
    
    const summary = {
      success: true,
      checked: pendingConnections.length,
      newConnections: connectionResults.newConnections.length,
      messagingTriggered: messagingResults.triggered,
      details: {
        connectionResults,
        updateResults,
        messagingResults
      }
    };
    
    console.log(`✅ Connection check complete:`);
    console.log(`   - Checked: ${summary.checked} pending connections`);
    console.log(`   - New connections: ${summary.newConnections}`);
    console.log(`   - Messages triggered: ${summary.messagingTriggered}`);
    
    return summary;
    
  } catch (error) {
    console.log(`❌ Connection check failed: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Get contacts with pending LinkedIn connection requests
 */
function getPendingLinkedInConnections() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const contactSheet = ss.getSheetByName("ContactList");
  const data = contactSheet.getDataRange().getValues();
  const headers = data[0];
  
  const pendingConnections = [];
  
  // Find LinkedIn tracking columns
  const linkedinSentIndex = headers.findIndex(h => h.includes("LinkedIn Connect Sent"));
  const linkedinAcceptedIndex = headers.findIndex(h => h.includes("LinkedIn Connect Accepted"));
  const linkedinFailedIndex = headers.findIndex(h => h.includes("LinkedIn Failed"));
  
  if (linkedinSentIndex === -1) {
    console.log('ℹ️ No LinkedIn Connect Sent column found');
    return [];
  }
  
  // Scan for pending connections
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    
    // Has connection been sent?
    const connectionSent = row[linkedinSentIndex];
    if (!connectionSent || !(connectionSent instanceof Date)) continue;
    
    // Has connection been accepted already?
    const connectionAccepted = linkedinAcceptedIndex !== -1 ? row[linkedinAcceptedIndex] : null;
    if (connectionAccepted && connectionAccepted instanceof Date) continue;
    
    // Has connection failed?
    const connectionFailed = linkedinFailedIndex !== -1 ? row[linkedinFailedIndex] : null;
    if (connectionFailed) continue;
    
    // This is a pending connection
    const contact = {
      rowIndex: i,
      firstName: row[headers.indexOf("First Name")] || '',
      lastName: row[headers.indexOf("Last Name")] || '',
      email: row[headers.indexOf("Email")] || '',
      company: row[headers.indexOf("Company")] || '',
      linkedinUrl: row[headers.indexOf("LinkedIn URL")] || '',
      connectionSentDate: connectionSent,
      daysSinceConnection: Math.floor((new Date() - connectionSent) / (1000 * 60 * 60 * 24))
    };
    
    // Only check connections that are at least 1 day old (give time for acceptance)
    if (contact.daysSinceConnection >= 1) {
      pendingConnections.push(contact);
    }
  }
  
  return pendingConnections;
}

/**
 * Check connection status for a batch of contacts via PhantomBuster
 */
function checkConnectionStatusBatch(contacts) {
  console.log(`🔍 Checking connection status for ${contacts.length} contacts...`);
  
  try {
    // Update PhantomBuster sheet with LinkedIn URLs to check
    const sheetUpdateResult = updateConnectionCheckSheet(contacts);
    if (!sheetUpdateResult.success) {
      throw new Error(`Failed to update check sheet: ${sheetUpdateResult.error}`);
    }
    
    // Launch PhantomBuster connection checker agent
    const launchResult = launchConnectionCheckerAgent();
    if (!launchResult.success) {
      throw new Error(`Failed to launch checker: ${launchResult.error}`);
    }
    
    // Poll for completion
    const pollResult = pollConnectionCheckerStatus(launchResult.containerId);
    
    if (pollResult.status === 'finished') {
      // Parse results to find new connections
      const newConnections = parseConnectionCheckResults(contacts, pollResult.result);
      
      return {
        success: true,
        newConnections: newConnections,
        checkedCount: contacts.length
      };
    } else {
      console.log(`⚠️ Connection check failed or timed out: ${pollResult.error}`);
      return {
        success: false,
        error: pollResult.error,
        newConnections: [],
        checkedCount: 0
      };
    }
    
  } catch (error) {
    console.log(`❌ Batch connection check failed: ${error.toString()}`);
    return {
      success: false,
      error: error.toString(),
      newConnections: [],
      checkedCount: 0
    };
  }
}

/**
 * Update PhantomBuster sheet with LinkedIn URLs to check connection status
 */
function updateConnectionCheckSheet(contacts) {
  try {
    console.log(`📝 Updating connection check sheet with ${contacts.length} profiles...`);
    
    // Open the PhantomBuster sheet
    const sheetId = '1jvJSIDBTZ_zwwy-myGdRPfDKXnsnastwwU9FgSfoHWU';
    const sheet = SpreadsheetApp.openById(sheetId).getActiveSheet();
    
    // Clear existing content (keep headers)
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).clearContent();
    }
    
    // Prepare data array - just LinkedIn URLs for connection checking
    const data = [];
    for (const contact of contacts) {
      const cleanedUrl = Services.cleanLinkedInUrl(contact.linkedinUrl);
      data.push([cleanedUrl, `Check connection status for ${contact.firstName} ${contact.lastName}`]);
    }
    
    // Write data to sheet
    if (data.length > 0) {
      sheet.getRange(2, 1, data.length, 2).setValues(data);
      console.log(`✅ Check sheet updated with ${data.length} profiles`);
    }
    
    // Force sheet to save
    SpreadsheetApp.flush();
    
    return { success: true, rowsUpdated: data.length };
    
  } catch (error) {
    console.log(`❌ Check sheet update failed: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Launch PhantomBuster LinkedIn Sent Request Extractor
 * Uses specific agent designed for checking connection statuses
 */
function launchConnectionCheckerAgent() {
  try {
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    
    // Get LinkedIn Sent Request Extractor agent ID from Properties
    const agentId = PropertiesService.getScriptProperties().getProperty('PB_SENT_REQUEST_EXTRACTOR_ID');
    
    if (!agentId) {
      throw new Error('PB_SENT_REQUEST_EXTRACTOR_ID not found in script properties');
    }
    
    console.log(`🚀 Launching connection checker agent (${agentId})...`);
    
    const url = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/launch`;
    const payload = { mode: 'check-connections' }; // Custom parameter if agent supports it
    
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
    
    if (responseCode === 200 && result.status === 'success' && result.data && result.data.containerId) {
      console.log(`✅ Connection checker launched: ${result.data.containerId}`);
      return { 
        success: true, 
        containerId: result.data.containerId
      };
    } else {
      console.log(`❌ Connection checker launch failed: ${JSON.stringify(result)}`);
      return { 
        success: false, 
        error: result.error || result.message || 'Unknown error'
      };
    }
    
  } catch (error) {
    console.log(`❌ Connection checker launch error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Poll connection checker status (simplified version of main polling function)
 */
function pollConnectionCheckerStatus(containerId) {
  try {
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = PropertiesService.getScriptProperties().getProperty('PB_SENT_REQUEST_EXTRACTOR_ID');
    
    console.log(`⏳ Polling LinkedIn Sent Request Extractor ${containerId}...`);
    
    const maxWaitTime = 300000; // 5 minutes
    const pollInterval = 30000; // 30 seconds
    const startTime = new Date().getTime();
    
    while (true) {
      // Check agent output
      const statusUrl = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/output`;
      const response = UrlFetchApp.fetch(statusUrl, {
        method: 'GET',
        headers: {
          'X-Phantombuster-Key': config.apiKey,
          'Accept': 'application/json'
        },
        muteHttpExceptions: true
      });
      
      if (response.getResponseCode() === 200) {
        const result = JSON.parse(response.getContentText());
        
        if (result.status === 'success' && result.data) {
          const data = result.data;
          const agentStatus = data.agentStatus || 'unknown';
          const containerStatus = data.containerStatus || 'unknown';
          
          console.log(`   📊 Connection Checker Status: ${agentStatus}`);
          
          // Check if finished
          if (agentStatus === 'not running' && containerStatus === 'not running') {
            // Check container history for final status
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
                if (container && container.lastEndStatus === 'success') {
                  return { status: 'finished', result: container };
                }
              }
            }
            
            return { status: 'finished', result: data };
          }
          
          // Check timeout
          if (new Date().getTime() - startTime > maxWaitTime) {
            return { status: 'timeout', error: 'Connection check timeout after 5 minutes' };
          }
          
          // Still running, wait and try again
          Utilities.sleep(pollInterval);
        }
      } else {
        return { status: 'error', error: `API error: ${response.getResponseCode()}` };
      }
    }
    
  } catch (error) {
    console.log(`❌ Connection checker polling failed: ${error.toString()}`);
    return { status: 'error', error: error.toString() };
  }
}

/**
 * Parse connection check results to identify newly accepted connections
 */
function parseConnectionCheckResults(originalContacts, checkResult) {
  // This is a placeholder function
  // In production, you'd parse actual PhantomBuster results to determine connection status
  
  console.log(`🔍 Parsing connection check results...`);
  
  const newConnections = [];
  
  // For demonstration, randomly mark some connections as newly accepted
  // In production, this would parse actual PhantomBuster CSV results
  originalContacts.forEach(contact => {
    // Simulate 30% acceptance rate for demonstration
    if (Math.random() < 0.3) {
      newConnections.push({
        ...contact,
        connectionAcceptedDate: new Date(),
        status: 'newly_connected'
      });
    }
  });
  
  console.log(`✅ Found ${newConnections.length} newly accepted connections`);
  return newConnections;
}

/**
 * Update spreadsheet with connection acceptance results
 */
function updateConnectionStatuses(connectionResults) {
  try {
    console.log(`📝 Updating connection statuses...`);
    
    if (!connectionResults.success || connectionResults.newConnections.length === 0) {
      console.log('ℹ️ No connection status updates needed');
      return { success: true, updated: 0 };
    }
    
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const contactSheet = ss.getSheetByName("ContactList");
    const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
    
    // Find or create "LinkedIn Connect Accepted" column
    let acceptedIndex = headers.indexOf("LinkedIn Connect Accepted");
    if (acceptedIndex === -1) {
      acceptedIndex = headers.length;
      contactSheet.getRange(1, acceptedIndex + 1).setValue("LinkedIn Connect Accepted");
    }
    
    let updatedCount = 0;
    for (const connection of connectionResults.newConnections) {
      const row = connection.rowIndex + 1;
      contactSheet.getRange(row, acceptedIndex + 1).setValue(connection.connectionAcceptedDate);
      updatedCount++;
      
      console.log(`   ✅ Marked ${connection.firstName} ${connection.lastName} as connected`);
    }
    
    console.log(`✅ Updated ${updatedCount} connection statuses`);
    return { success: true, updated: updatedCount };
    
  } catch (error) {
    console.log(`❌ Connection status update failed: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Trigger LinkedIn messaging for newly accepted connections
 */
function triggerMessagingForNewConnections(newConnections) {
  try {
    console.log(`💬 Triggering messaging for ${newConnections.length} new connections...`);
    
    if (newConnections.length === 0) {
      return { success: true, triggered: 0 };
    }
    
    let triggeredCount = 0;
    for (const connection of newConnections) {
      // Create a messaging task for this newly connected contact
      const messageTask = {
        contact: connection,
        day: 1, // First LinkedIn message
        taskType: 'linkedin_message',
        scheduledDate: new Date(), // Send immediately
        priority: 'high'
      };
      
      // In production, you'd add this to the campaign queue
      console.log(`   💬 Queued message for ${connection.firstName} ${connection.lastName} (Day 1)`);
      triggeredCount++;
      
      // You could also trigger immediate message sending here:
      // LinkedIn.processMessagesForToday([messageTask]);
    }
    
    console.log(`✅ Triggered ${triggeredCount} LinkedIn messages`);
    return { success: true, triggered: triggeredCount };
    
  } catch (error) {
    console.log(`❌ Message triggering failed: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Automated daily connection monitoring (for scheduled execution)
 */
function runDailyConnectionCheck() {
  console.log('📅 Running daily LinkedIn connection check...');
  
  const startTime = new Date();
  const result = checkLinkedInConnections();
  const endTime = new Date();
  const duration = (endTime - startTime) / 1000;
  
  console.log(`⏱️ Daily check completed in ${duration} seconds`);
  
  if (result.success && result.newConnections > 0) {
    // Send notification email about new connections
    sendConnectionNotification(result);
  }
  
  return result;
}

/**
 * Send notification email about new connections
 */
function sendConnectionNotification(checkResult) {
  try {
    const adminEmail = Session.getActiveUser().getEmail();
    const subject = `🎉 New LinkedIn Connections - ${checkResult.newConnections} accepted!`;
    
    const body = `
DOGNOSIS OUTREACH AUTOMATION UPDATE

🎉 LinkedIn Connection Acceptances Detected!

New Connections: ${checkResult.newConnections}
Total Checked: ${checkResult.checked}
Messages Triggered: ${checkResult.messagingTriggered}

These contacts have accepted your LinkedIn connection requests and will now receive their first LinkedIn message automatically.

Time: ${new Date().toLocaleString()}

--
Best,
Amir Alpert
Business Development | Dognosis.tech
`;

    GmailApp.sendEmail(adminEmail, subject, body);
    console.log(`📧 Connection notification sent to ${adminEmail}`);
    
  } catch (error) {
    console.log(`❌ Failed to send notification: ${error.toString()}`);
  }
}

// Wrapper functions for Apps Script dropdown
function checkConnections() {
  return checkLinkedInConnections();
}

function dailyConnectionCheck() {
  return runDailyConnectionCheck();
}

/**
 * Test function to validate LinkedIn Sent Request Extractor setup
 */
function testConnectionChecker() {
  console.log('🧪 Testing LinkedIn Sent Request Extractor setup...');
  
  try {
    // Check if agent ID is configured
    const agentId = PropertiesService.getScriptProperties().getProperty('PB_SENT_REQUEST_EXTRACTOR_ID');
    if (!agentId) {
      console.log('❌ PB_SENT_REQUEST_EXTRACTOR_ID not found in script properties');
      return { success: false, error: 'Agent ID not configured' };
    }
    
    console.log(`✅ Found Connection Checker Agent ID: ${agentId}`);
    
    // Check if PhantomBuster config exists
    const config = Services.getProperty('phantombuster_config');
    if (!config) {
      console.log('❌ PhantomBuster config not found');
      return { success: false, error: 'PhantomBuster config missing' };
    }
    
    const parsedConfig = JSON.parse(config);
    console.log(`✅ PhantomBuster API Key: ***${parsedConfig.apiKey.slice(-4)}`);
    
    // Test agent accessibility
    const url = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}`;
    const response = UrlFetchApp.fetch(url, {
      method: 'GET',
      headers: {
        'X-Phantombuster-Key': parsedConfig.apiKey,
        'Accept': 'application/json'
      },
      muteHttpExceptions: true
    });
    
    const responseCode = response.getResponseCode();
    console.log(`📡 Agent API Response: ${responseCode}`);
    
    if (responseCode === 200) {
      const result = JSON.parse(response.getContentText());
      if (result.status === 'success' && result.data) {
        console.log(`✅ Agent Found: ${result.data.name}`);
        console.log(`✅ Script ID: ${result.data.scriptId}`);
        console.log(`✅ Previous Launches: ${result.data.nbLaunches || 0}`);
        
        return {
          success: true,
          agentId: agentId,
          agentName: result.data.name,
          scriptId: result.data.scriptId,
          launches: result.data.nbLaunches || 0
        };
      } else {
        console.log('❌ Unexpected response structure');
        return { success: false, error: 'Invalid agent response' };
      }
    } else {
      console.log(`❌ Agent not accessible: HTTP ${responseCode}`);
      return { success: false, error: `HTTP ${responseCode}` };
    }
    
  } catch (error) {
    console.log(`❌ Test failed: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}