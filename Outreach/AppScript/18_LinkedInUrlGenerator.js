// ======================
// DOGNOSIS OUTREACH AUTOMATION - LINKEDIN URL GENERATOR
// Generate LinkedIn search URLs from company and keyword combinations
// ======================

const LinkedInUrlGenerator = {
  /**
   * Generate LinkedIn search URLs from input data
   */
  generateLinkedInUrls: function() {
    try {
      console.log("🔗 Starting LinkedIn URL generation...");
      
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const sheet = ss.getSheetByName("LinkedIn_URLs");
      
      if (!sheet) {
        console.log("❌ LinkedIn_URLs sheet not found");
        return { success: false, error: "LinkedIn_URLs sheet not found" };
      }
      
      const data = sheet.getDataRange().getValues();
      const headers = data[0];
      
      // Find column indexes
      const companyIndex = headers.indexOf("Company");
      const keywordGroupIndex = headers.indexOf("Keyword Group"); 
      const keywordsUsedIndex = headers.indexOf("Keywords Used");
      let longUrlIndex = headers.indexOf("Long URL");
      
      // Create Long URL column if it doesn't exist
      if (longUrlIndex === -1) {
        longUrlIndex = headers.length;
        sheet.getRange(1, longUrlIndex + 1).setValue("Long URL");
        console.log("✅ Added 'Long URL' column");
      }
      
      let urlsGenerated = 0;
      
      // Process each row
      for (let row = 1; row < data.length; row++) {
        const company = data[row][companyIndex];
        const keywordGroup = data[row][keywordGroupIndex];
        const keywordsUsed = data[row][keywordsUsedIndex];
        
        if (company && keywordGroup && keywordsUsed) {
          // Convert comma-separated to OR format
          const processedKeywords = this.convertToOrFormat(keywordsUsed);
          const linkedInUrl = this.buildLinkedInSearchUrl(company, processedKeywords);
          
          // Write URL to Long URL column
          sheet.getRange(row + 1, longUrlIndex + 1).setValue(linkedInUrl);
          urlsGenerated++;
        }
      }
      
      console.log(`✅ Generated ${urlsGenerated} LinkedIn URLs in existing sheet`);
      return { success: true, urlCount: urlsGenerated, sheet: "LinkedIn_URLs" };
      
    } catch (error) {
      console.log(`❌ Error generating LinkedIn URLs: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },

  /**
   * Setup or get the input sheet - no hardcoded data
   */
  setupInputSheet: function() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let inputSheet = ss.getSheetByName("LinkedIn_URLs");
    
    if (!inputSheet) {
      console.log("📝 Creating LinkedIn_URLs sheet...");
      inputSheet = ss.insertSheet("LinkedIn_URLs");
      
      // Add only headers - user will populate data
      const headers = [
        ["Company Names", "Executive Keywords", "BD Keywords", "Sales Keywords", "Technical Keywords"]
      ];
      
      inputSheet.getRange(1, 1, 1, headers[0].length).setValues(headers);
      
      // Format the sheet
      inputSheet.getRange(1, 1, 1, headers[0].length).setFontWeight("bold").setBackground("#4285f4").setFontColor("white");
      inputSheet.getRange("B:E").setWrap(true);
      inputSheet.setColumnWidth(1, 150); // Company column
      inputSheet.setColumnWidth(2, 300); // Executive keywords
      inputSheet.setColumnWidth(3, 300); // BD keywords  
      inputSheet.setColumnWidth(4, 300); // Sales keywords
      inputSheet.setColumnWidth(5, 300); // Technical keywords
      
      console.log("✅ Created LinkedIn_URLs sheet with headers only");
    }
    
    return inputSheet;
  },

  /**
   * Setup or get the output sheet
   */
  setupOutputSheet: function() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let outputSheet = ss.getSheetByName("LinkedIn_URLs_Output");
    
    if (!outputSheet) {
      outputSheet = ss.insertSheet("LinkedIn_URLs_Output");
      console.log("📊 Created LinkedIn_URLs_Output sheet");
    } else {
      // Clear existing data
      outputSheet.clear();
    }
    
    // Add headers
    const headers = [
      "Company", "Keyword Group", "Keywords Used", "LinkedIn Search URL", "Generated Date"
    ];
    
    outputSheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    outputSheet.getRange(1, 1, 1, headers.length).setFontWeight("bold").setBackground("#34a853").setFontColor("white");
    
    // Set column widths
    outputSheet.setColumnWidth(1, 120); // Company
    outputSheet.setColumnWidth(2, 100); // Keyword Group
    outputSheet.setColumnWidth(3, 250); // Keywords Used
    outputSheet.setColumnWidth(4, 500); // LinkedIn URL - wider for full URL
    outputSheet.setColumnWidth(5, 120); // Date
    
    return outputSheet;
  },

  /**
   * Process URL generation from input data
   */
  processUrlGeneration: function(inputData, outputSheet) {
    const headers = inputData[0];
    const companies = [];
    const keywordGroups = {};
    
    // Parse headers to identify keyword columns
    for (let col = 1; col < headers.length; col++) {
      const header = headers[col];
      if (header && header.trim() !== "") {
        keywordGroups[header] = col;
      }
    }
    
    console.log(`📋 Found keyword groups: ${Object.keys(keywordGroups).join(', ')}`);
    
    // Extract companies and their data
    for (let row = 1; row < inputData.length; row++) {
      const companyName = inputData[row][0];
      if (companyName && companyName.trim() !== "") {
        const companyData = { name: companyName, keywords: {} };
        
        // Get keywords for each group
        for (const [groupName, colIndex] of Object.entries(keywordGroups)) {
          const keywords = inputData[row][colIndex];
          if (keywords && keywords.trim() !== "") {
            // Convert comma-separated keywords to OR format
            const processedKeywords = this.convertToOrFormat(keywords.trim());
            companyData.keywords[groupName] = processedKeywords;
          }
        }
        
        companies.push(companyData);
      }
    }
    
    console.log(`🏢 Processing ${companies.length} companies`);
    
    // Generate URLs for each combination
    const outputData = [];
    let urlCount = 0;
    
    for (const company of companies) {
      for (const [groupName, keywords] of Object.entries(company.keywords)) {
        const linkedInUrl = this.buildLinkedInSearchUrl(company.name, keywords);
        
        outputData.push([
          company.name,
          groupName,
          keywords,
          linkedInUrl,
          new Date()
        ]);
        
        urlCount++;
      }
    }
    
    // Write output data
    if (outputData.length > 0) {
      outputSheet.getRange(2, 1, outputData.length, 5).setValues(outputData);
      
      // Format URLs column to show full URL
      const urlRange = outputSheet.getRange(2, 4, outputData.length, 1);
      urlRange.setWrap(true);
      
      console.log(`📊 Added ${outputData.length} URL combinations to output sheet`);
    }
    
    return {
      success: true,
      urlCount: urlCount,
      companyCount: companies.length,
      keywordGroups: Object.keys(keywordGroups).length,
      outputSheet: "LinkedIn_URLs_Output"
    };
  },

  /**
   * Build LinkedIn search URL from company and keywords
   */
  buildLinkedInSearchUrl: function(companyName, keywords) {
    const baseUrl = "https://www.linkedin.com/search/results/people/";
    
    // Clean keywords first - remove line breaks and extra spaces
    const cleanedKeywords = keywords
      .replace(/\r?\n/g, ' ')        // Remove line breaks
      .replace(/\s+/g, ' ')          // Replace multiple spaces with single space
      .trim();                       // Remove leading/trailing spaces
    
    // URL encode the company name and cleaned keywords
    const encodedCompany = encodeURIComponent(companyName);
    const encodedKeywords = encodeURIComponent(cleanedKeywords);
    
    // Build the full URL with parameters
    const fullUrl = `${baseUrl}?company=${encodedCompany}&keywords=${encodedKeywords}&origin=GLOBAL_SEARCH_HEADER`;
    
    return fullUrl;
  },

  /**
   * Convert comma-separated keywords to OR format (LinkedIn-optimized)
   */
  convertToOrFormat: function(commaSeparatedKeywords) {
    const keywords = commaSeparatedKeywords
      .split(',')
      .map(keyword => keyword.trim())
      .filter(keyword => keyword.length > 0);
    
    // Limit to maximum 7 OR conditions for LinkedIn compatibility
    const limitedKeywords = keywords.slice(0, 7);
    
    if (keywords.length > 7) {
      console.log(`⚠️ Truncated ${keywords.length} keywords to ${limitedKeywords.length} for LinkedIn compatibility`);
    }
    
    return limitedKeywords
      .join(' OR ')
      .replace(/\s+/g, ' ')  // Replace multiple spaces with single space
      .trim();               // Remove leading/trailing spaces
  },

  /**
   * Process simplified CSV format (Company, Keyword Group, Keywords Used)
   */
  processSimplifiedFormat: function(inputData) {
    try {
      console.log("📄 Processing simplified CSV format...");
      
      // Get or create output sheet
      const outputSheet = this.setupOutputSheet();
      
      // Process each row
      const outputData = [];
      let urlCount = 0;
      let missingKeywords = 0;
      
      for (let row = 1; row < inputData.length; row++) {
        const company = inputData[row][0];
        const keywordGroup = inputData[row][1];
        const keywordsUsed = inputData[row][2];
        
        if (company && keywordGroup) {
          if (keywordsUsed && keywordsUsed.trim() !== "") {
            // Convert comma-separated to OR format
            const processedKeywords = this.convertToOrFormat(keywordsUsed.trim());
            const linkedInUrl = this.buildLinkedInSearchUrl(company, processedKeywords);
            
            outputData.push([
              company,
              keywordGroup,
              processedKeywords,
              linkedInUrl,
              new Date()
            ]);
            
            urlCount++;
          } else {
            missingKeywords++;
            console.log(`⚠️ No keywords for ${company} - ${keywordGroup}`);
          }
        }
      }
      
      // Write output data
      if (outputData.length > 0) {
        outputSheet.getRange(2, 1, outputData.length, 5).setValues(outputData);
        console.log(`📊 Added ${outputData.length} URL combinations to output sheet`);
      }
      
      const message = missingKeywords > 0 ? 
        `Generated ${urlCount} URLs. ${missingKeywords} rows missing keywords.` :
        `Successfully generated ${urlCount} URLs`;
      
      return {
        success: true,
        urlCount: urlCount,
        missingKeywords: missingKeywords,
        outputSheet: "LinkedIn_URLs_Output",
        message: message
      };
      
    } catch (error) {
      console.log(`❌ Error processing simplified format: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },

  /**
   * Generate URLs for specific company and keyword group
   */
  generateSingleUrl: function(companyName, keywords) {
    try {
      const url = this.buildLinkedInSearchUrl(companyName, keywords);
      console.log(`🔗 Generated URL for ${companyName}:`);
      console.log(url);
      return { success: true, url: url, company: companyName };
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },

  /**
   * Add new company to input sheet
   */
  addCompanyToInput: function(companyName, keywordData = {}) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const inputSheet = ss.getSheetByName("LinkedIn_URLs");
      
      if (!inputSheet) {
        console.log("❌ LinkedIn_URLs sheet not found");
        return { success: false, error: "Input sheet not found" };
      }
      
      const headers = inputSheet.getRange(1, 1, 1, inputSheet.getLastColumn()).getValues()[0];
      const newRow = [companyName];
      
      // Add keyword data for each column
      for (let col = 1; col < headers.length; col++) {
        const header = headers[col];
        newRow.push(keywordData[header] || "");
      }
      
      // Add the new row
      const lastRow = inputSheet.getLastRow();
      inputSheet.getRange(lastRow + 1, 1, 1, newRow.length).setValues([newRow]);
      
      console.log(`✅ Added ${companyName} to input sheet`);
      return { success: true, company: companyName, row: lastRow + 1 };
      
    } catch (error) {
      console.log(`❌ Error adding company: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  }
};

// Top-level wrapper functions for Apps Script dropdown
function generateLinkedInUrls() {
  return LinkedInUrlGenerator.generateLinkedInUrls();
}

function addCompanyForLinkedInSearch(companyName, keywordData = {}) {
  return LinkedInUrlGenerator.addCompanyToInput(companyName, keywordData);
}


function generateSingleLinkedInUrl(companyName, keywords) {
  return LinkedInUrlGenerator.generateSingleUrl(companyName, keywords);
}

// Quick test function
function testLinkedInUrlGenerator() {
  console.log("🧪 Testing LinkedIn URL Generator...");
  
  // Test comma-separated to OR conversion
  const testKeywords = "CEO, CFO, COO, President, VP";
  const convertedKeywords = LinkedInUrlGenerator.convertToOrFormat(testKeywords);
  console.log(`Original: ${testKeywords}`);
  console.log(`Converted: ${convertedKeywords}`);
  
  // Test single URL generation
  const testResult = LinkedInUrlGenerator.generateSingleUrl(
    "Exact Sciences", 
    convertedKeywords
  );
  
  console.log("Test Result:");
  console.log(testResult);
  
  return testResult;
}