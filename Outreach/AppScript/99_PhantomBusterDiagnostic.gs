/**
 * PHANTOMBUSTER API STEP-BY-STEP DIAGNOSTIC
 * Validates each step of the API workflow individually
 */

/**
 * Step 1: Verify agent exists and is accessible
 */
function step1_VerifyAgent() {
  console.log('🔍 STEP 1: VERIFY AGENT EXISTS');
  console.log('==================================');
  
  try {
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = config.networkBoosterId;
    const apiKey = config.apiKey;
    
    console.log(`Agent ID: ${agentId}`);
    console.log(`API Key: ***${apiKey.slice(-4)}`);
    
    // Construct URL
    const agentUrl = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}`;
    console.log(`Agent URL: ${agentUrl}`);
    
    // Prepare headers
    const headers = {
      'X-Phantombuster-Key': apiKey,
      'Accept': 'application/json'
    };
    console.log(`Headers: ${JSON.stringify(headers, null, 2)}`);
    
    // Make API call
    console.log('📡 Making API call...');
    const response = UrlFetchApp.fetch(agentUrl, {
      method: 'GET',
      headers: headers,
      muteHttpExceptions: true
    });
    
    // Validate response code
    const responseCode = response.getResponseCode();
    console.log(`✅ Response Code: ${responseCode}`);
    
    // Validate content type
    const contentType = response.getHeaders()['Content-Type'] || 'Unknown';
    console.log(`✅ Content-Type: ${contentType}`);
    
    // Get response body
    const responseText = response.getContentText();
    console.log(`✅ Response Length: ${responseText.length} characters`);
    console.log(`✅ Response Preview: ${responseText.substring(0, 200)}...`);
    
    // Parse JSON
    if (contentType.includes('application/json')) {
      try {
        const parsedResponse = JSON.parse(responseText);
        console.log(`✅ JSON Valid: YES`);
        console.log(`✅ Full Response: ${JSON.stringify(parsedResponse, null, 2)}`);
        
        // Validate structure
        if (parsedResponse.status === 'success' && parsedResponse.data) {
          console.log(`✅ Agent Found: ${parsedResponse.data.name}`);
          console.log(`✅ Agent State: ${parsedResponse.data.state || 'Unknown'}`);
          console.log(`✅ Script ID: ${parsedResponse.data.scriptId || 'Unknown'}`);
          
          return { success: true, agent: parsedResponse.data };
        } else {
          console.log(`❌ Unexpected JSON structure`);
          return { success: false, error: 'Unexpected JSON structure' };
        }
      } catch (jsonError) {
        console.log(`❌ JSON Parse Error: ${jsonError.toString()}`);
        return { success: false, error: 'Invalid JSON' };
      }
    } else {
      console.log(`❌ Not JSON response`);
      return { success: false, error: 'Not JSON response' };
    }
    
  } catch (error) {
    console.log(`❌ Step 1 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Step 2: Prepare and validate launch payload
 */
function step2_PrepareLaunch() {
  console.log('\n🚀 STEP 2: PREPARE LAUNCH PAYLOAD');
  console.log('===================================');
  
  try {
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = config.networkBoosterId;
    const apiKey = config.apiKey;
    
    // Construct launch URL
    const launchUrl = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/launch`;
    console.log(`Launch URL: ${launchUrl}`);
    
    // Prepare payload
    const payload = {}; // Empty for basic launch
    console.log(`Payload: ${JSON.stringify(payload)}`);
    console.log(`Payload String: ${JSON.stringify(payload)}`);
    console.log(`Payload Length: ${JSON.stringify(payload).length}`);
    
    // Prepare headers
    const headers = {
      'X-Phantombuster-Key': apiKey,
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };
    console.log(`Headers: ${JSON.stringify(headers, null, 2)}`);
    
    // Validate URL format
    if (!launchUrl.includes('/launch')) {
      console.log(`❌ URL missing /launch endpoint`);
      return { success: false, error: 'Invalid launch URL' };
    }
    
    if (!apiKey || apiKey.length < 10) {
      console.log(`❌ API key appears invalid`);
      return { success: false, error: 'Invalid API key' };
    }
    
    console.log(`✅ Launch preparation complete`);
    console.log(`✅ Ready to launch agent ${agentId}`);
    
    return { 
      success: true, 
      launchUrl: launchUrl,
      payload: payload,
      headers: headers 
    };
    
  } catch (error) {
    console.log(`❌ Step 2 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Step 3: Execute launch API call with full validation
 */
function step3_ExecuteLaunch() {
  console.log('\n🎯 STEP 3: EXECUTE LAUNCH API CALL');
  console.log('===================================');
  
  try {
    // Get launch preparation
    const prep = step2_PrepareLaunch();
    if (!prep.success) {
      console.log(`❌ Launch preparation failed: ${prep.error}`);
      return prep;
    }
    
    console.log('📡 Making launch API call...');
    console.log(`URL: ${prep.launchUrl}`);
    console.log(`Method: POST`);
    
    // Make the API call
    const response = UrlFetchApp.fetch(prep.launchUrl, {
      method: 'POST',
      headers: prep.headers,
      payload: JSON.stringify(prep.payload),
      muteHttpExceptions: true
    });
    
    // Validate response code
    const responseCode = response.getResponseCode();
    console.log(`✅ Response Code: ${responseCode}`);
    
    // Get all response headers
    const responseHeaders = response.getHeaders();
    console.log(`✅ Response Headers:`);
    Object.keys(responseHeaders).forEach(key => {
      console.log(`   ${key}: ${responseHeaders[key]}`);
    });
    
    // Get response body
    const responseText = response.getContentText();
    console.log(`✅ Response Length: ${responseText.length} characters`);
    console.log(`✅ Raw Response: ${responseText}`);
    
    // Validate content type
    const contentType = responseHeaders['Content-Type'] || 'Unknown';
    if (!contentType.includes('application/json')) {
      console.log(`❌ Expected JSON, got: ${contentType}`);
      return { success: false, error: `Non-JSON response: ${contentType}` };
    }
    
    // Parse JSON response
    let parsedResponse;
    try {
      parsedResponse = JSON.parse(responseText);
      console.log(`✅ JSON Parse: SUCCESS`);
      console.log(`✅ Parsed Response: ${JSON.stringify(parsedResponse, null, 2)}`);
    } catch (jsonError) {
      console.log(`❌ JSON Parse Error: ${jsonError.toString()}`);
      return { success: false, error: 'JSON parse failed', rawResponse: responseText };
    }
    
    // Validate response structure
    if (responseCode === 200) {
      if (parsedResponse.status === 'success') {
        if (parsedResponse.data && parsedResponse.data.containerId) {
          const containerId = parsedResponse.data.containerId;
          console.log(`✅ LAUNCH SUCCESS!`);
          console.log(`✅ Container ID: ${containerId}`);
          
          // Store container ID for next steps
          PropertiesService.getScriptProperties().setProperty('diagnostic_container_id', containerId);
          
          return { 
            success: true, 
            containerId: containerId,
            response: parsedResponse 
          };
        } else {
          console.log(`❌ Missing containerId in response`);
          console.log(`Expected: {status: 'success', data: {containerId: '...'}}`);
          return { success: false, error: 'Missing containerId', response: parsedResponse };
        }
      } else {
        console.log(`❌ API returned error status: ${parsedResponse.status}`);
        return { success: false, error: parsedResponse.message || 'API error', response: parsedResponse };
      }
    } else {
      console.log(`❌ HTTP Error: ${responseCode}`);
      return { success: false, error: `HTTP ${responseCode}`, response: parsedResponse };
    }
    
  } catch (error) {
    console.log(`❌ Step 3 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Step 4: Check agent status immediately after launch
 */
function step4_CheckStatusImmediate() {
  console.log('\n📊 STEP 4: CHECK STATUS IMMEDIATELY');
  console.log('====================================');
  
  try {
    const containerId = PropertiesService.getScriptProperties().getProperty('diagnostic_container_id');
    if (!containerId) {
      console.log(`❌ No container ID found. Run step3_ExecuteLaunch() first.`);
      return { success: false, error: 'No container ID' };
    }
    
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = config.networkBoosterId;
    const apiKey = config.apiKey;
    
    console.log(`Looking for Container: ${containerId}`);
    console.log(`Agent ID: ${agentId}`);
    
    // Check agent output
    const statusUrl = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/output`;
    console.log(`Status URL: ${statusUrl}`);
    
    const response = UrlFetchApp.fetch(statusUrl, {
      method: 'GET',
      headers: {
        'X-Phantombuster-Key': apiKey,
        'Accept': 'application/json'
      },
      muteHttpExceptions: true
    });
    
    console.log(`Status Response Code: ${response.getResponseCode()}`);
    const statusText = response.getContentText();
    console.log(`Status Response: ${statusText}`);
    
    const statusData = JSON.parse(statusText);
    
    if (statusData.status === 'success' && statusData.data) {
      const data = statusData.data;
      
      console.log(`✅ Agent Status: ${data.agentStatus}`);
      console.log(`✅ Container Status: ${data.containerStatus}`);
      console.log(`✅ Current Container: ${data.containerId}`);
      console.log(`✅ Running Containers: ${data.runningContainers}`);
      console.log(`✅ Queued Containers: ${data.queuedContainers}`);
      
      if (data.progress) {
        console.log(`✅ Progress: ${JSON.stringify(data.progress)}`);
      }
      
      // Check container matching
      if (data.containerId === containerId) {
        console.log(`✅ CONTAINER MATCH: Agent is running our container`);
      } else {
        console.log(`⚠️ CONTAINER MISMATCH:`);
        console.log(`   Expected: ${containerId}`);
        console.log(`   Current:  ${data.containerId}`);
      }
      
      return {
        success: true,
        agentStatus: data.agentStatus,
        containerMatch: data.containerId === containerId,
        runningContainers: data.runningContainers,
        data: data
      };
      
    } else {
      console.log(`❌ Invalid status response structure`);
      return { success: false, error: 'Invalid response', response: statusData };
    }
    
  } catch (error) {
    console.log(`❌ Step 4 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Step 5: Check container history for final results
 */
function step5_CheckContainerHistory() {
  console.log('\n📜 STEP 5: CHECK CONTAINER HISTORY');
  console.log('===================================');
  
  try {
    const containerId = PropertiesService.getScriptProperties().getProperty('diagnostic_container_id');
    if (!containerId) {
      console.log(`❌ No container ID found.`);
      return { success: false, error: 'No container ID' };
    }
    
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = config.networkBoosterId;
    const apiKey = config.apiKey;
    
    console.log(`Looking for Container: ${containerId}`);
    
    const containersUrl = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/containers`;
    console.log(`Containers URL: ${containersUrl}`);
    
    const response = UrlFetchApp.fetch(containersUrl, {
      method: 'GET',
      headers: {
        'X-Phantombuster-Key': apiKey,
        'Accept': 'application/json'
      },
      muteHttpExceptions: true
    });
    
    console.log(`Containers Response Code: ${response.getResponseCode()}`);
    const containersText = response.getContentText();
    console.log(`Containers Response Length: ${containersText.length}`);
    
    const containersData = JSON.parse(containersText);
    
    if (containersData.status === 'success' && containersData.data) {
      console.log(`✅ Found ${containersData.data.length} container runs total`);
      
      // Show recent containers
      console.log(`✅ Recent containers:`);
      containersData.data.slice(0, 3).forEach((container, index) => {
        console.log(`   ${index + 1}. ID: ${container.id}`);
        console.log(`      Launch: ${new Date(container.launchDate)}`);
        console.log(`      Status: ${container.lastEndStatus}`);
        if (container.id === containerId) {
          console.log(`      👆 THIS IS OUR CONTAINER!`);
        }
      });
      
      // Find our specific container
      const ourContainer = containersData.data.find(c => c.id === containerId);
      
      if (ourContainer) {
        console.log(`\n✅ FOUND OUR CONTAINER:`);
        console.log(`   ID: ${ourContainer.id}`);
        console.log(`   Launch Date: ${new Date(ourContainer.launchDate)}`);
        console.log(`   End Date: ${new Date(ourContainer.endDate)}`);
        console.log(`   Final Status: ${ourContainer.lastEndStatus}`);
        console.log(`   Exit Code: ${ourContainer.exitCode}`);
        console.log(`   Duration: ${ourContainer.endDate - ourContainer.launchDate}ms`);
        
        if (ourContainer.lastEndStatus === 'success') {
          console.log(`🎉 CONTAINER COMPLETED SUCCESSFULLY!`);
        } else {
          console.log(`❌ Container failed with status: ${ourContainer.lastEndStatus}`);
        }
        
        return {
          success: true,
          found: true,
          container: ourContainer,
          finalStatus: ourContainer.lastEndStatus
        };
        
      } else {
        console.log(`❌ Our container ${containerId} not found in history`);
        console.log(`   Available IDs: ${containersData.data.map(c => c.id).join(', ')}`);
        return { success: false, found: false, error: 'Container not in history' };
      }
      
    } else {
      console.log(`❌ Invalid containers response`);
      return { success: false, error: 'Invalid response', response: containersData };
    }
    
  } catch (error) {
    console.log(`❌ Step 5 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Run all diagnostic steps in sequence
 */
function runFullPhantomBusterDiagnostic() {
  console.log('🔬 PHANTOMBUSTER API FULL DIAGNOSTIC');
  console.log('=====================================');
  console.log('This will run all 5 steps in sequence\n');
  
  const results = {
    timestamp: new Date().toISOString(),
    steps: []
  };
  
  // Step 1: Verify Agent
  const step1 = step1_VerifyAgent();
  results.steps.push({ step: 1, name: 'Verify Agent', ...step1 });
  if (!step1.success) {
    console.log('\n❌ DIAGNOSTIC FAILED AT STEP 1');
    return results;
  }
  
  // Step 2: Prepare Launch
  const step2 = step2_PrepareLaunch();
  results.steps.push({ step: 2, name: 'Prepare Launch', ...step2 });
  if (!step2.success) {
    console.log('\n❌ DIAGNOSTIC FAILED AT STEP 2');
    return results;
  }
  
  // Step 3: Execute Launch
  const step3 = step3_ExecuteLaunch();
  results.steps.push({ step: 3, name: 'Execute Launch', ...step3 });
  if (!step3.success) {
    console.log('\n❌ DIAGNOSTIC FAILED AT STEP 3');
    return results;
  }
  
  // Wait a moment for agent to start
  console.log('\n⏳ Waiting 10 seconds for agent to start...');
  Utilities.sleep(10000);
  
  // Step 4: Check Status
  const step4 = step4_CheckStatusImmediate();
  results.steps.push({ step: 4, name: 'Check Status', ...step4 });
  
  // Step 5: Check History
  const step5 = step5_CheckContainerHistory();
  results.steps.push({ step: 5, name: 'Check History', ...step5 });
  
  // Summary
  console.log('\n📊 DIAGNOSTIC SUMMARY:');
  results.steps.forEach(step => {
    console.log(`${step.success ? '✅' : '❌'} Step ${step.step}: ${step.name}`);
  });
  
  const passed = results.steps.filter(s => s.success).length;
  console.log(`\n${passed}/5 steps passed`);
  
  return results;
}