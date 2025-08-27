// ======================
// DOGNOSIS OUTREACH AUTOMATION - TEST DOMAIN
// Comprehensive testing and validation system
// ======================

const Test = {
  /**
   * Run fast-forward live test with real contacts
   * Accelerated timeline for complete sequence testing
   */
  runFastForward: function() {
    console.log("⚡ FAST FORWARD TEST - Real automation in accelerated time");
    
    const testResults = {
      success: true,
      startTime: new Date(),
      totalContacts: 0,
      emailsSent: 0,
      linkedinConnectsSent: 0,
      linkedinMessagesSent: 0,
      errors: [],
      timeline: []
    };
    
    try {
      // Get active contacts
      const contacts = this.getActiveContacts();
      testResults.totalContacts = contacts.length;
      
      if (contacts.length === 0) {
        console.log("⚠️ No active contacts found for testing");
        return { success: false, error: "No contacts available for testing" };
      }
      
      console.log(`👥 Testing with ${contacts.length} active contacts`);
      
      // Get sequence configuration for first contact (assuming all use same sequence)
      const sequenceConfig = Services.getContactSequenceConfig(contacts[0].sequenceSheet);
      if (!sequenceConfig) {
        throw new Error(`Invalid sequence: ${contacts[0].sequenceSheet}`);
      }
      
      console.log(`📋 Using sequence: ${contacts[0].sequenceSheet}`);
      console.log(`📅 Email days: ${sequenceConfig.emailDays.join(', ')}`);
      console.log(`🤝 LinkedIn connect days: ${sequenceConfig.linkedinConnectDays.join(', ')}`);
      console.log(`💬 LinkedIn message days: ${sequenceConfig.linkedinMessageDays.join(', ')}`);
      
      // Calculate all action days
      const allActionDays = [...new Set([
        ...sequenceConfig.emailDays,
        ...sequenceConfig.linkedinConnectDays, 
        ...sequenceConfig.linkedinMessageDays
      ])].sort((a, b) => a - b);
      
      console.log(`🚀 Processing ${allActionDays.length} sequence days in 10 minutes...`);
      
      // Process each day in accelerated time
      for (let i = 0; i < allActionDays.length && i < 10; i++) {
        const day = allActionDays[i];
        console.log(`\n📅 MINUTE ${i}: Processing Day ${day} actions`);
        
        // Process emails for this day
        if (sequenceConfig.emailDays.includes(day)) {
          const emailResults = this.processEmailsForDay(contacts, day);
          testResults.emailsSent += emailResults.sent;
          testResults.errors.push(...emailResults.errors);
          console.log(`   📧 Emails sent: ${emailResults.sent}`);
        }
        
        // Process LinkedIn connects for this day  
        if (sequenceConfig.linkedinConnectDays.includes(day)) {
          const connectResults = this.processLinkedInConnectsForDay(contacts, day);
          testResults.linkedinConnectsSent += connectResults.sent;
          testResults.errors.push(...connectResults.errors);
          console.log(`   🤝 LinkedIn connects: ${connectResults.sent}`);
        }
        
        // Process LinkedIn messages for this day
        if (sequenceConfig.linkedinMessageDays.includes(day)) {
          const messageResults = this.processLinkedInMessagesForDay(contacts, day);
          testResults.linkedinMessagesSent += messageResults.sent;
          testResults.errors.push(...messageResults.errors);
          console.log(`   💬 LinkedIn messages: ${messageResults.sent}`);
        }
        
        // Wait 1 minute before next batch (compressed time)
        if (i < allActionDays.length - 1) {
          console.log(`   ⏳ Waiting 1 minute...`);
          Utilities.sleep(60000);
        }
      }
      
      // Final results
      const endTime = new Date();
      const duration = (endTime - testResults.startTime) / 1000;
      
      console.log("\n" + "=".repeat(50));
      console.log("🎯 FAST FORWARD TEST COMPLETE");
      console.log("=".repeat(50));
      console.log(`⏱️ Duration: ${Math.round(duration)} seconds`);
      console.log(`👥 Contacts processed: ${testResults.totalContacts}`);
      console.log(`📧 Emails sent: ${testResults.emailsSent}`);
      console.log(`🤝 LinkedIn connects: ${testResults.linkedinConnectsSent}`);
      console.log(`💬 LinkedIn messages: ${testResults.linkedinMessagesSent}`);
      console.log(`❌ Errors: ${testResults.errors.length}`);
      
      if (testResults.errors.length === 0) {
        console.log("\n🎉 ALL TESTS PASSED! System is working perfectly.");
        testResults.success = true;
      } else {
        console.log("\n⚠️ Some issues encountered:");
        testResults.errors.slice(0, 5).forEach(error => console.log(`   • ${error}`));
        testResults.success = false;
      }
      
      return testResults;
      
    } catch (error) {
      console.log(`💥 Test failed: ${error.toString()}`);
      testResults.success = false;
      testResults.errors.push(error.toString());
      return testResults;
    }
  },
  
  /**
   * Run comprehensive system check
   */
  runSystemCheck: function() {
    console.log("🔍 SYSTEM CHECK - Validating all components");
    
    const checks = {
      success: true,
      results: [],
      errors: []
    };
    
    try {
      // Check 1: Gmail integration
      console.log("1️⃣ Testing Gmail integration...");
      const gmailResult = this.testEmailIntegration();
      checks.results.push({ component: "Gmail", success: gmailResult.success });
      if (!gmailResult.success) checks.errors.push(`Gmail: ${gmailResult.error}`);
      
      // Check 2: PhantomBuster API
      console.log("2️⃣ Testing PhantomBuster API...");
      const pbResult = this.testLinkedInAPI();
      checks.results.push({ component: "PhantomBuster", success: pbResult.success });
      if (!pbResult.success) checks.errors.push(`PhantomBuster: ${pbResult.error}`);
      
      // Check 3: Spreadsheet access
      console.log("3️⃣ Testing spreadsheet access...");
      const sheetResult = this.testSpreadsheetAccess();
      checks.results.push({ component: "Spreadsheet", success: sheetResult.success });
      if (!sheetResult.success) checks.errors.push(`Spreadsheet: ${sheetResult.error}`);
      
      // Check 4: Sequence validation
      console.log("4️⃣ Testing sequence configuration...");
      const sequenceResult = this.testSequenceValidation();
      checks.results.push({ component: "Sequences", success: sequenceResult.success });
      if (!sequenceResult.success) checks.errors.push(`Sequences: ${sequenceResult.error}`);
      
      // Determine overall success
      checks.success = checks.errors.length === 0;
      
      if (checks.success) {
        console.log("✅ All system checks passed!");
      } else {
        console.log(`⚠️ ${checks.errors.length} issues found:`);
        checks.errors.forEach(error => console.log(`   ❌ ${error}`));
      }
      
      return checks;
      
    } catch (error) {
      console.log(`💥 System check failed: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Test email integration
   */
  testEmailIntegration: function() {
    try {
      // Check Gmail quota
      const quota = MailApp.getRemainingDailyQuota();
      if (quota < VALIDATION.MIN_GMAIL_QUOTA) {
        return { success: false, error: `Low Gmail quota: ${quota} remaining` };
      }
      
      // Send test email to self
      const testEmail = Session.getActiveUser().getEmail();
      MailApp.sendEmail(
        testEmail,
        "Dognosis Test Email",
        "This is a test email from Dognosis Automation System. Gmail integration is working!"
      );
      
      console.log(`   ✅ Test email sent to ${testEmail}`);
      return { success: true };
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Test LinkedIn API integration
   */
  testLinkedInAPI: function() {
    try {
      const config = Services.getProperty('phantombuster_config');
      if (!config) {
        return { success: false, error: "PhantomBuster not configured" };
      }
      
      const parsedConfig = JSON.parse(config);
      
      // Test API connection
      const response = LinkedIn.testConnection();
      if (!response.success) {
        return { success: false, error: response.error };
      }
      
      console.log("   ✅ PhantomBuster API connection successful");
      return { success: true };
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Test spreadsheet access
   */
  testSpreadsheetAccess: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      
      if (!contactSheet) {
        return { success: false, error: "ContactList sheet not found" };
      }
      
      const contactCount = contactSheet.getLastRow() - 1;
      console.log(`   ✅ ContactList accessible with ${contactCount} contacts`);
      return { success: true, contactCount };
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Test sequence validation
   */
  testSequenceValidation: function() {
    try {
      const sequenceSheets = Services.getAllSequenceSheets();
      if (sequenceSheets.length === 0) {
        return { success: false, error: "No sequence sheets found" };
      }
      
      let validSequences = 0;
      for (const sheetName of sequenceSheets) {
        const config = Services.getContactSequenceConfig(sheetName);
        if (config && config.isValid()) {
          validSequences++;
        }
      }
      
      console.log(`   ✅ ${validSequences}/${sequenceSheets.length} sequences valid`);
      return { success: validSequences === sequenceSheets.length };
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Get active contacts for testing
   */
  getActiveContacts: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      const getColIndex = name => headers.indexOf(name);
      
      const activeContacts = [];
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        const contact = Services.createContactFromRow(row, headers, i);
        
        if (contact.isValid() && !contact.paused && contact.campaignStartDate) {
          activeContacts.push(contact);
        }
      }
      
      return activeContacts;
      
    } catch (error) {
      console.log(`Error getting active contacts: ${error.toString()}`);
      return [];
    }
  },
  
  /**
   * Process emails for specific day
   */
  processEmailsForDay: function(contacts, day) {
    const results = { sent: 0, errors: [] };
    
    for (const contact of contacts) {
      try {
        const emailResult = Email.sendForDay(contact, day);
        if (emailResult.success) {
          results.sent++;
        } else {
          results.errors.push(`${contact.firstName}: ${emailResult.error}`);
        }
      } catch (error) {
        results.errors.push(`${contact.firstName}: ${error.toString()}`);
      }
    }
    
    return results;
  },
  
  /**
   * Process LinkedIn connects for specific day
   */
  processLinkedInConnectsForDay: function(contacts, day) {
    const results = { sent: 0, errors: [] };
    
    try {
      // Batch process LinkedIn connects
      const connectTasks = contacts.map(contact => ({
        contact: contact,
        day: day
      }));
      
      const batchResult = LinkedIn.processConnectionsForToday(connectTasks);
      results.sent = batchResult.successCount || 0;
      results.errors = batchResult.errors || [];
      
    } catch (error) {
      results.errors.push(`Batch LinkedIn connects: ${error.toString()}`);
    }
    
    return results;
  },
  
  /**
   * Process LinkedIn messages for specific day
   */
  processLinkedInMessagesForDay: function(contacts, day) {
    const results = { sent: 0, errors: [] };
    
    try {
      // Batch process LinkedIn messages
      const messageTasks = contacts.map(contact => ({
        contact: contact,
        day: day
      }));
      
      const batchResult = LinkedIn.processMessagesForToday(messageTasks);
      results.sent = batchResult.successCount || 0;
      results.errors = batchResult.errors || [];
      
    } catch (error) {
      results.errors.push(`Batch LinkedIn messages: ${error.toString()}`);
    }
    
    return results;
  }
};

// Top-level wrapper functions for Apps Script dropdown visibility
function runFastForward() {
  return Test.runFastForward();
}

function runSystemCheck() {
  return Test.runSystemCheck();
}

function testEmailIntegration() {
  return Test.testEmailIntegration();
}

function testLinkedInAPI() {
  return Test.testLinkedInAPI();
}

function testSpreadsheetAccess() {
  return Test.testSpreadsheetAccess();
}

function testSequenceValidation() {
  return Test.testSequenceValidation();
}

function getActiveContacts() {
  return Test.getActiveContacts();
}

function processEmailsForDay(contacts, day) {
  return Test.processEmailsForDay(contacts, day);
}

function processLinkedInConnectsForDay(contacts, day) {
  return Test.processLinkedInConnectsForDay(contacts, day);
}

function processLinkedInMessagesForDay(contacts, day) {
  return Test.processLinkedInMessagesForDay(contacts, day);
}

// Legacy function support for backward compatibility
function runFastForwardLiveTest() {
  console.log("ℹ️ Legacy function called - redirecting to Test.runFastForward()");
  return Test.runFastForward();
}

function testSystem() {
  console.log("ℹ️ Legacy function called - redirecting to Test.runSystemCheck()");
  return Test.runSystemCheck();
}