// ======================
// DOGNOSIS OUTREACH AUTOMATION - SPREADSHEET OPTIMIZER
// Optimized spreadsheet structure with data validation
// ======================

const SpreadsheetOptimizer = {
  /**
   * Create optimized ContactList structure
   */
  createOptimizedContactList: function() {
    console.log("🔄 Creating optimized ContactList structure...");
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      
      // Create new optimized sheet
      const newSheet = ss.insertSheet("ContactList_Optimized");
      
      // Define optimized column structure
      const optimizedHeaders = [
        // CORE CONTACT INFORMATION (Columns A-F) - CRM Order
        "First Name",      // A - Essential for personalization  
        "Last Name",       // B - Essential for personalization
        "Title",           // C - Important for targeting
        "Company",         // D - Essential for personalization
        "Email",           // E - Primary key
        "LinkedIn URL",    // F - Important for LinkedIn outreach
        
        // CAMPAIGN MANAGEMENT (Columns G-K)
        "Sequence",        // G - Which sequence they're in
        "Campaign Start Date", // H - When campaign started
        "Status",          // I - Active/Paused/Completed/Replied
        "Priority",        // J - High/Medium/Low
        "Source",          // K - Where contact came from
        
        // COMMUNICATION TRACKING (Columns L-P)
        "Last Contact Date",   // L - When last contacted
        "Reply Date",         // M - When they replied
        "Reply Channel",      // N - Email/LinkedIn
        "Response Type",      // O - Positive/Negative/Neutral
        "Next Action",        // P - What to do next
        
        // METADATA (Columns Q-S)
        "Created Date",       // Q - When added to system
        "Last Modified",      // R - When last updated
        "Notes"              // S - Additional notes
      ];
      
      // Set headers with formatting
      const headerRange = newSheet.getRange(1, 1, 1, optimizedHeaders.length);
      headerRange.setValues([optimizedHeaders]);
      headerRange.setFontWeight("bold");
      headerRange.setBackground("#4285f4");
      headerRange.setFontColor("white");
      
      // Add data validation
      this.addContactListValidation(newSheet, optimizedHeaders);
      
      // Add conditional formatting
      this.addContactListFormatting(newSheet, optimizedHeaders);
      
      // Freeze header row
      newSheet.setFrozenRows(1);
      
      // Auto-resize columns
      newSheet.autoResizeColumns(1, optimizedHeaders.length);
      
      console.log(`✅ Created optimized ContactList with ${optimizedHeaders.length} columns`);
      
      return {
        success: true,
        sheet: newSheet,
        headers: optimizedHeaders,
        message: "Optimized ContactList created successfully"
      };
      
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.createOptimizedContactList', error);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Create optimized Sequence structure  
   */
  createOptimizedSequence: function(sequenceName = "ExecSeq_Optimized") {
    console.log(`🔄 Creating optimized sequence: ${sequenceName}...`);
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      
      // Create new sequence sheet
      const newSheet = ss.insertSheet(sequenceName);
      
      // Define optimized sequence structure
      const optimizedHeaders = [
        // ACTION DEFINITION (Columns A-C)
        "Day",            // A - Sequence day number
        "Action Type",    // B - Email/LinkedIn_Connect/LinkedIn_Message
        "Email Type",     // C - Initial/Reply/Follow_Up
        
        // CONTENT (Columns D-E)
        "Subject",        // D - Email subject line
        "Message Content", // E - Email body or LinkedIn message
        
        // METADATA (Columns F-G)
        "Description",    // F - Brief description of this step
        "Notes"          // G - Internal notes
      ];
      
      // Set headers with formatting
      const headerRange = newSheet.getRange(1, 1, 1, optimizedHeaders.length);
      headerRange.setValues([optimizedHeaders]);
      headerRange.setFontWeight("bold");
      headerRange.setBackground("#34a853");
      headerRange.setFontColor("white");
      
      // Add data validation
      this.addSequenceValidation(newSheet, optimizedHeaders);
      
      // Add conditional formatting
      this.addSequenceFormatting(newSheet, optimizedHeaders);
      
      // Add sample data with standardized placeholders
      this.addSampleSequenceData(newSheet, optimizedHeaders);
      
      // Freeze header row
      newSheet.setFrozenRows(1);
      
      // Auto-resize columns
      newSheet.autoResizeColumns(1, optimizedHeaders.length);
      
      console.log(`✅ Created optimized sequence: ${sequenceName}`);
      
      return {
        success: true,
        sheet: newSheet,
        headers: optimizedHeaders,
        message: `Optimized sequence ${sequenceName} created successfully`
      };
      
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.createOptimizedSequence', error);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Add data validation to ContactList
   */
  addContactListValidation: function(sheet, headers) {
    try {
      const lastRow = Math.max(sheet.getLastRow(), 100); // Plan for 100 rows
      
      // Email validation (Column E)
      const emailColumn = headers.indexOf("Email") + 1;
      if (emailColumn > 0) {
        const emailRange = sheet.getRange(2, emailColumn, lastRow - 1, 1);
        const emailValidation = SpreadsheetApp.newDataValidation()
          .requireFormulaSatisfied('=AND(ISERROR(FIND(" ",E2))=TRUE,ISERROR(FIND("@",E2))=FALSE)')
          .setAllowInvalid(false)
          .setHelpText("Please enter a valid email address")
          .build();
        emailRange.setDataValidation(emailValidation);
      }
      
      // Sequence validation (Column G) - Dynamic list of sheets ending with "Seq"
      const sequenceColumn = headers.indexOf("Sequence") + 1;
      if (sequenceColumn > 0) {
        const sequenceSheets = this.getSequenceSheetNames();
        if (sequenceSheets.length > 0) {
          const sequenceRange = sheet.getRange(2, sequenceColumn, lastRow - 1, 1);
          const sequenceValidation = SpreadsheetApp.newDataValidation()
            .requireValueInList(sequenceSheets, true)
            .setAllowInvalid(false)
            .setHelpText(`Select sequence: ${sequenceSheets.join(", ")}`)
            .build();
          sequenceRange.setDataValidation(sequenceValidation);
        }
      }
      
      // Status validation (Column I)
      const statusColumn = headers.indexOf("Status") + 1;
      if (statusColumn > 0) {
        const statusRange = sheet.getRange(2, statusColumn, lastRow - 1, 1);
        const statusValidation = SpreadsheetApp.newDataValidation()
          .requireValueInList(["Active", "Paused", "Completed", "Replied"], true)
          .setAllowInvalid(false)
          .setHelpText("Select: Active, Paused, Completed, or Replied")
          .build();
        statusRange.setDataValidation(statusValidation);
      }
      
      // Priority validation (Column J)
      const priorityColumn = headers.indexOf("Priority") + 1;
      if (priorityColumn > 0) {
        const priorityRange = sheet.getRange(2, priorityColumn, lastRow - 1, 1);
        const priorityValidation = SpreadsheetApp.newDataValidation()
          .requireValueInList(["High", "Medium", "Low"], true)
          .setAllowInvalid(false)
          .setHelpText("Select: High, Medium, or Low")
          .build();
        priorityRange.setDataValidation(priorityValidation);
      }
      
      // Response Type validation (Column O)
      const responseColumn = headers.indexOf("Response Type") + 1;
      if (responseColumn > 0) {
        const responseRange = sheet.getRange(2, responseColumn, lastRow - 1, 1);
        const responseValidation = SpreadsheetApp.newDataValidation()
          .requireValueInList(["Positive", "Negative", "Neutral", "Interested", "Not Interested"], true)
          .setAllowInvalid(true)
          .setHelpText("Select response type (optional)")
          .build();
        responseRange.setDataValidation(responseValidation);
      }
      
      console.log("✅ Added data validation to ContactList");
      
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.addContactListValidation', error);
    }
  },
  
  /**
   * Add data validation to Sequence sheet
   */
  addSequenceValidation: function(sheet, headers) {
    try {
      const lastRow = Math.max(sheet.getLastRow(), 50); // Plan for 50 rows
      
      // Day validation (Column A) - must be positive integer
      const dayColumn = headers.indexOf("Day") + 1;
      if (dayColumn > 0) {
        const dayRange = sheet.getRange(2, dayColumn, lastRow - 1, 1);
        const dayValidation = SpreadsheetApp.newDataValidation()
          .requireNumberGreaterThan(0)
          .setAllowInvalid(false)
          .setHelpText("Enter a positive day number (1, 2, 3, etc.)")
          .build();
        dayRange.setDataValidation(dayValidation);
      }
      
      // Action Type validation (Column B)
      const actionColumn = headers.indexOf("Action Type") + 1;
      if (actionColumn > 0) {
        const actionRange = sheet.getRange(2, actionColumn, lastRow - 1, 1);
        const actionValidation = SpreadsheetApp.newDataValidation()
          .requireValueInList(["Email", "LinkedIn_Connect", "LinkedIn_Message"], true)
          .setAllowInvalid(false)
          .setHelpText("Select: Email, LinkedIn_Connect, or LinkedIn_Message")
          .build();
        actionRange.setDataValidation(actionValidation);
      }
      
      // Email Type validation (Column C)
      const emailTypeColumn = headers.indexOf("Email Type") + 1;
      if (emailTypeColumn > 0) {
        const emailTypeRange = sheet.getRange(2, emailTypeColumn, lastRow - 1, 1);
        const emailTypeValidation = SpreadsheetApp.newDataValidation()
          .requireValueInList(["Initial", "Reply", "Follow_Up"], true)
          .setAllowInvalid(true)
          .setHelpText("Select: Initial, Reply, or Follow_Up (for emails only)")
          .build();
        emailTypeRange.setDataValidation(emailTypeValidation);
      }
      
      console.log("✅ Added data validation to sequence sheet");
      
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.addSequenceValidation', error);
    }
  },
  
  /**
   * Add conditional formatting to ContactList
   */
  addContactListFormatting: function(sheet, headers) {
    try {
      const lastRow = Math.max(sheet.getLastRow(), 100);
      
      // Status column formatting
      const statusColumn = headers.indexOf("Status") + 1;
      if (statusColumn > 0) {
        const statusRange = sheet.getRange(2, statusColumn, lastRow - 1, 1);
        
        // Green for Active
        const activeRule = SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo("Active")
          .setBackground("#d9ead3")
          .setFontColor("#0d5016")
          .setRanges([statusRange])
          .build();
        
        // Red for Paused
        const pausedRule = SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo("Paused")
          .setBackground("#f4cccc")
          .setFontColor("#cc0000")
          .setRanges([statusRange])
          .build();
        
        // Blue for Completed
        const completedRule = SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo("Completed")
          .setBackground("#cfe2f3")
          .setFontColor("#1155cc")
          .setRanges([statusRange])
          .build();
        
        sheet.setConditionalFormatRules([activeRule, pausedRule, completedRule]);
      }
      
      // Priority column formatting
      const priorityColumn = headers.indexOf("Priority") + 1;
      if (priorityColumn > 0) {
        const priorityRange = sheet.getRange(2, priorityColumn, lastRow - 1, 1);
        
        const highPriorityRule = SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo("High")
          .setBackground("#fce5cd")
          .setFontColor("#e69138")
          .setRanges([priorityRange])
          .build();
        
        const existingRules = sheet.getConditionalFormatRules();
        sheet.setConditionalFormatRules([...existingRules, highPriorityRule]);
      }
      
      console.log("✅ Added conditional formatting to ContactList");
      
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.addContactListFormatting', error);
    }
  },
  
  /**
   * Add conditional formatting to Sequence sheet
   */
  addSequenceFormatting: function(sheet, headers) {
    try {
      const lastRow = Math.max(sheet.getLastRow(), 50);
      
      // Action Type column formatting
      const actionColumn = headers.indexOf("Action Type") + 1;
      if (actionColumn > 0) {
        const actionRange = sheet.getRange(2, actionColumn, lastRow - 1, 1);
        
        // Email actions - blue
        const emailRule = SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo("Email")
          .setBackground("#cfe2f3")
          .setFontColor("#1155cc")
          .setRanges([actionRange])
          .build();
        
        // LinkedIn Connect - green
        const linkedinConnectRule = SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo("LinkedIn_Connect")
          .setBackground("#d9ead3")
          .setFontColor("#0d5016")
          .setRanges([actionRange])
          .build();
        
        // LinkedIn Message - yellow
        const linkedinMessageRule = SpreadsheetApp.newConditionalFormatRule()
          .whenTextEqualTo("LinkedIn_Message")
          .setBackground("#fff2cc")
          .setFontColor("#bf9000")
          .setRanges([actionRange])
          .build();
        
        sheet.setConditionalFormatRules([emailRule, linkedinConnectRule, linkedinMessageRule]);
      }
      
      console.log("✅ Added conditional formatting to sequence sheet");
      
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.addSequenceFormatting', error);
    }
  },
  
  /**
   * Add sample data to sequence with standardized placeholders - ALL 10 STEPS
   */
  addSampleSequenceData: function(sheet, headers) {
    try {
      const sampleData = [
        [1, "Email", "Initial", "Improving MCED Early Stage Sensitivity", 
         "Hi {First Name},\n\nEven best-in-class MCED tests miss what's not shedding.\n\nWe've developed a breath-based test that, when paired with liquid biopsy, can significantly improve stage 1/2 detection, and overall test sensitivity.\n\nCan I send you our white paper?", 
         "Initial email", "Early stage cancer → multi-modal with breath, increased test performance"],
        
        [3, "LinkedIn_Connect", "", "", 
         "Hi {First Name}, I lead BD at Dognosis where we're pairing breath analysis with MCED to improve stage 1/2 detection. Would love to connect.", 
         "Initial LinkedIn connection request", "I want to talk to you about detecting early stage cancers by MCED"],
        
        [5, "LinkedIn_Message", "", "", 
         "Appreciate you connecting. I'd love to share how we're working to improve MCED test sensitivity and support earlier detection in population screening.", 
         "Initial LinkedIn message", "Thanks for accepting my connection, I'm reaching out to talk about increasing MCED test performance and improving stage shift in general population screening"],
        
        [8, "Email", "Initial", "Better Payer Metrics for MCED", 
         "Hi {First Name},\n\nPayers need strong sensitivity and clear ROI to support MCED coverage.\n\nAt Dognosis, we combine breath testing with liquid biopsy to improve early-stage detection and key payer metrics like PPV and cost per cancer detected.\n\nThis multi-modal approach may help close the gap between clinical potential and commercial viability.\n\nCan I send a brief overview?", 
         "Second email", "Reimbursement strategy → multi-modal with breath increases test performance, while improving payer metrics"],
        
        [11, "Email", "Reply", "", 
         "Hi {First Name},\n\nFollowing up to see if you had a chance to review my last note.", 
         "Third email, follow up", "Just wanted to bring this to the top of your inbox"],
        
        [14, "Email", "Initial", "Cleaner, Quicker, MCED Trials", 
         "Hi {First Name},\n\nRunning large, well-powered trials is one of the biggest hurdles to demonstrating value in early cancer detection. Our breath-based test is fully remote and easy to deploy—making it possible to design broader studies without adding operational complexity.\n\nBy combining this with liquid biopsy, we've found it meaningfully improves early-stage detection and sensitivity metrics.\n\nCan I send over a one-pager?", 
         "Fourth email", "Reducing the cost of large clinical trials → better outreach and higher acceptance"],
        
        [17, "LinkedIn_Message", "", "", 
         "Following up here in case you missed my earlier message—keen to share something relevant to your work.", 
         "Second LinkedIn message", "Hoping to bring this to the top of your message inbox, hopefully we can discuss"],
        
        [20, "Email", "Initial", "Redefining MCED - Liquid Biopsy 2.0", 
         "Hi {First Name},\n\nMCED is a land grab right now—but most platforms are converging on the same limited approach.\n\nRather than compete head-to-head on ctDNA alone, we see an opportunity to collaborate and help define what the next generation of MCED can be.\n\nWe've built a breath test that pairs with liquid biopsy to boost early-stage detection and reshape what's possible.\n\nCare to discuss what this paradigm would look like?", 
         "Fifth email", "Commercial differentiation → multimodal in MCED when everyone is sticking with single mode approaches"],
        
        [23, "Email", "Initial", "Cancer has a Smell", 
         "Hi {First Name},\n\n\"Daisy kept staring at me and lunging into my chest... Had it not been drawn to my attention by Daisy, I'm told my prognosis would have been very poor.\"- Claire Guest, Medical Detection Dogs, CNN, 2016\n\nThese stories stay with us at Dognosis. Now we're chasing the deeper question: how can we combine breath and blood together.\n\nWould love to discuss a model where positive cases from our breath test feed into your liquid biopsy testing.", 
         "Sixth email", "Cancer case study"],
        
        [27, "Email", "Initial", "Final Note from Dognosis", 
         "Hi {First Name},\n\nThis will be my last note — I'll give your inbox a break.\n\nOver the last few emails, I've shared how Dognosis is pairing breath testing with liquid biopsy to boost early-stage detection and create a more differentiated, multimodal MCED approach. The goal: better sensitivity, simplified clinical trial design, and a clearer reimbursement story.\n\nIf this is something you'd be open to exploring, I'd be happy to send a short data brief or set up a quick call.", 
         "Seventh and final email", "Last email, will give your inbox a break, summary and final call to action"]
      ];
      
      const dataRange = sheet.getRange(2, 1, sampleData.length, headers.length);
      dataRange.setValues(sampleData);
      
      console.log(`✅ Added ${sampleData.length} sample sequence rows`);
      
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.addSampleSequenceData', error);
    }
  },
  
  /**
   * Get all sheet names ending with "Seq"
   */
  getSequenceSheetNames: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const allSheets = ss.getSheets();
      
      return allSheets
        .map(sheet => sheet.getName())
        .filter(name => name.endsWith("Seq"))
        .sort();
        
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.getSequenceSheetNames', error);
      return ["ExecSeq"]; // Fallback
    }
  },

  /**
   * Run complete optimization
   */
  optimizeSpreadsheetStructure: function() {
    console.log("🚀 Starting complete spreadsheet optimization...");
    
    const results = {
      success: true,
      contactList: null,
      sequence: null,
      errors: []
    };
    
    try {
      // Create optimized ContactList
      const contactResult = this.createOptimizedContactList();
      results.contactList = contactResult;
      if (!contactResult.success) {
        results.errors.push(`ContactList: ${contactResult.error}`);
      }
      
      // Create optimized Sequence
      const sequenceResult = this.createOptimizedSequence();
      results.sequence = sequenceResult;
      if (!sequenceResult.success) {
        results.errors.push(`Sequence: ${sequenceResult.error}`);
      }
      
      results.success = results.errors.length === 0;
      
      if (results.success) {
        console.log("✅ Spreadsheet optimization complete!");
        console.log("   📋 ContactList_Optimized created with data validation");
        console.log("   📋 ExecSeq_Optimized created with sample data");
      }
      
      return results;
      
    } catch (error) {
      Services.logError('SpreadsheetOptimizer.optimizeSpreadsheetStructure', error);
      results.success = false;
      results.errors.push(error.toString());
      return results;
    }
  }
};

// Legacy function support
function createOptimizedSpreadsheet() {
  return SpreadsheetOptimizer.optimizeSpreadsheetStructure();
}

function createOptimizedContactList() {
  return SpreadsheetOptimizer.createOptimizedContactList();
}

function createOptimizedSequence(name) {
  return SpreadsheetOptimizer.createOptimizedSequence(name);
}