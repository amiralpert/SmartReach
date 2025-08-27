/**
 * PHANTOMBUSTER MESSAGE API DIAGNOSTIC
 * Tests the LinkedIn messaging agent separately from connection agent
 */

/**
 * Step 1: Verify MESSAGE agent exists and is accessible
 */
function messageStep1_VerifyAgent() {
  console.log('🔍 MESSAGE STEP 1: VERIFY AGENT EXISTS');
  console.log('==========================================');
  
  try {
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = config.messageSenderId; // MESSAGE AGENT
    const apiKey = config.apiKey;
    
    console.log(`Message Agent ID: ${agentId}`);
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
    
    // Validate response
    const responseCode = response.getResponseCode();
    console.log(`✅ Response Code: ${responseCode}`);
    
    const contentType = response.getHeaders()['Content-Type'] || 'Unknown';
    console.log(`✅ Content-Type: ${contentType}`);
    
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
          console.log(`✅ Message Agent Found: ${parsedResponse.data.name}`);
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
    console.log(`❌ Message Step 1 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Step 2: Prepare MESSAGE agent launch payload
 */
function messageStep2_PrepareLaunch() {
  console.log('\n🚀 MESSAGE STEP 2: PREPARE LAUNCH PAYLOAD');
  console.log('==========================================');
  
  try {
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = config.messageSenderId; // MESSAGE AGENT
    const apiKey = config.apiKey;
    
    // Construct launch URL
    const launchUrl = `${PHANTOMBUSTER.API_BASE_URL}/agent/${agentId}/launch`;
    console.log(`Launch URL: ${launchUrl}`);
    
    // Prepare payload
    const payload = {}; // Empty for basic launch
    console.log(`Payload: ${JSON.stringify(payload)}`);
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
    
    console.log(`✅ Message agent launch preparation complete`);
    console.log(`✅ Ready to launch message agent ${agentId}`);
    
    return { 
      success: true, 
      launchUrl: launchUrl,
      payload: payload,
      headers: headers 
    };
    
  } catch (error) {
    console.log(`❌ Message Step 2 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Step 3: Execute MESSAGE agent launch
 */
function messageStep3_ExecuteLaunch() {
  console.log('\n🎯 MESSAGE STEP 3: EXECUTE LAUNCH API CALL');
  console.log('==========================================');
  
  try {
    // Get launch preparation
    const prep = messageStep2_PrepareLaunch();
    if (!prep.success) {
      console.log(`❌ Launch preparation failed: ${prep.error}`);
      return prep;
    }
    
    console.log('📡 Making MESSAGE agent launch API call...');
    console.log(`URL: ${prep.launchUrl}`);
    console.log(`Method: POST`);
    
    // Make the API call
    const response = UrlFetchApp.fetch(prep.launchUrl, {
      method: 'POST',
      headers: prep.headers,
      payload: JSON.stringify(prep.payload),
      muteHttpExceptions: true
    });
    
    // Validate response
    const responseCode = response.getResponseCode();
    console.log(`✅ Response Code: ${responseCode}`);
    
    const responseHeaders = response.getHeaders();
    console.log(`✅ Response Headers:`);
    Object.keys(responseHeaders).forEach(key => {
      console.log(`   ${key}: ${responseHeaders[key]}`);
    });
    
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
          console.log(`✅ MESSAGE AGENT LAUNCH SUCCESS!`);
          console.log(`✅ Container ID: ${containerId}`);
          
          // Store container ID for next steps
          PropertiesService.getScriptProperties().setProperty('message_diagnostic_container_id', containerId);
          
          return { 
            success: true, 
            containerId: containerId,
            response: parsedResponse 
          };
        } else {
          console.log(`❌ Missing containerId in response`);
          return { success: false, error: 'Missing containerId', response: parsedResponse };
        }
      } else {
        console.log(`❌ API returned error status: ${parsedResponse.status}`);
        console.log(`❌ Error message: ${parsedResponse.error || parsedResponse.message || 'Unknown'}`);
        return { success: false, error: parsedResponse.error || parsedResponse.message || 'API error', response: parsedResponse };
      }
    } else {
      console.log(`❌ HTTP Error: ${responseCode}`);
      return { success: false, error: `HTTP ${responseCode}`, response: parsedResponse };
    }
    
  } catch (error) {
    console.log(`❌ Message Step 3 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Step 4: Check MESSAGE agent status
 */
function messageStep4_CheckStatus() {
  console.log('\n📊 MESSAGE STEP 4: CHECK STATUS');
  console.log('================================');
  
  try {
    const containerId = PropertiesService.getScriptProperties().getProperty('message_diagnostic_container_id');
    if (!containerId) {
      console.log(`❌ No message container ID found. Run messageStep3_ExecuteLaunch() first.`);
      return { success: false, error: 'No container ID' };
    }
    
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = config.messageSenderId; // MESSAGE AGENT
    const apiKey = config.apiKey;
    
    console.log(`Looking for Message Container: ${containerId}`);
    console.log(`Message Agent ID: ${agentId}`);
    
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
      
      console.log(`✅ Message Agent Status: ${data.agentStatus}`);
      console.log(`✅ Container Status: ${data.containerStatus}`);
      console.log(`✅ Current Container: ${data.containerId}`);
      console.log(`✅ Running Containers: ${data.runningContainers}`);
      console.log(`✅ Queued Containers: ${data.queuedContainers}`);
      
      if (data.progress) {
        console.log(`✅ Progress: ${JSON.stringify(data.progress)}`);
      }
      
      // Check container matching
      if (data.containerId === containerId) {
        console.log(`✅ CONTAINER MATCH: Message agent is running our container`);
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
    console.log(`❌ Message Step 4 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Step 5: Check MESSAGE agent container history
 */
function messageStep5_CheckContainerHistory() {
  console.log('\n📜 MESSAGE STEP 5: CHECK CONTAINER HISTORY');
  console.log('==========================================');
  
  try {
    const containerId = PropertiesService.getScriptProperties().getProperty('message_diagnostic_container_id');
    if (!containerId) {
      console.log(`❌ No message container ID found.`);
      return { success: false, error: 'No container ID' };
    }
    
    const config = JSON.parse(Services.getProperty('phantombuster_config'));
    const agentId = config.messageSenderId; // MESSAGE AGENT
    const apiKey = config.apiKey;
    
    console.log(`Looking for Message Container: ${containerId}`);
    
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
      console.log(`✅ Found ${containersData.data.length} message container runs total`);
      
      // Show recent containers
      console.log(`✅ Recent message containers:`);
      containersData.data.slice(0, 3).forEach((container, index) => {
        console.log(`   ${index + 1}. ID: ${container.id}`);
        console.log(`      Launch: ${new Date(container.launchDate)}`);
        console.log(`      Status: ${container.lastEndStatus}`);
        if (container.id === containerId) {
          console.log(`      👆 THIS IS OUR MESSAGE CONTAINER!`);
        }
      });
      
      // Find our specific container
      const ourContainer = containersData.data.find(c => c.id === containerId);
      
      if (ourContainer) {
        console.log(`\n✅ FOUND OUR MESSAGE CONTAINER:`);
        console.log(`   ID: ${ourContainer.id}`);
        console.log(`   Launch Date: ${new Date(ourContainer.launchDate)}`);
        console.log(`   End Date: ${new Date(ourContainer.endDate)}`);
        console.log(`   Final Status: ${ourContainer.lastEndStatus}`);
        console.log(`   Exit Code: ${ourContainer.exitCode}`);
        console.log(`   Duration: ${ourContainer.endDate - ourContainer.launchDate}ms`);
        
        if (ourContainer.lastEndStatus === 'success') {
          console.log(`🎉 MESSAGE CONTAINER COMPLETED SUCCESSFULLY!`);
        } else {
          console.log(`❌ Message container failed with status: ${ourContainer.lastEndStatus}`);
        }
        
        return {
          success: true,
          found: true,
          container: ourContainer,
          finalStatus: ourContainer.lastEndStatus
        };
        
      } else {
        console.log(`❌ Our message container ${containerId} not found in history`);
        console.log(`   Available IDs: ${containersData.data.map(c => c.id).join(', ')}`);
        return { success: false, found: false, error: 'Container not in history' };
      }
      
    } else {
      console.log(`❌ Invalid containers response`);
      return { success: false, error: 'Invalid response', response: containersData };
    }
    
  } catch (error) {
    console.log(`❌ Message Step 5 Error: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

/**
 * Run all MESSAGE agent diagnostic steps in sequence
 */
function runFullMessageAgentDiagnostic() {
  console.log('🔬 PHANTOMBUSTER MESSAGE AGENT DIAGNOSTIC');
  console.log('==========================================');
  console.log('Testing LinkedIn MESSAGE agent separately\n');
  
  const results = {
    timestamp: new Date().toISOString(),
    agentType: 'MESSAGE_AGENT',
    steps: []
  };
  
  // Step 1: Verify Message Agent
  const step1 = messageStep1_VerifyAgent();
  results.steps.push({ step: 1, name: 'Verify Message Agent', ...step1 });
  if (!step1.success) {
    console.log('\n❌ MESSAGE DIAGNOSTIC FAILED AT STEP 1');
    return results;
  }
  
  // Step 2: Prepare Launch
  const step2 = messageStep2_PrepareLaunch();
  results.steps.push({ step: 2, name: 'Prepare Message Launch', ...step2 });
  if (!step2.success) {
    console.log('\n❌ MESSAGE DIAGNOSTIC FAILED AT STEP 2');
    return results;
  }
  
  // Step 3: Execute Launch
  const step3 = messageStep3_ExecuteLaunch();
  results.steps.push({ step: 3, name: 'Execute Message Launch', ...step3 });
  if (!step3.success) {
    console.log('\n❌ MESSAGE DIAGNOSTIC FAILED AT STEP 3');
    return results;
  }
  
  // Wait for agent to start
  console.log('\n⏳ Waiting 10 seconds for message agent to start...');
  Utilities.sleep(10000);
  
  // Step 4: Check Status
  const step4 = messageStep4_CheckStatus();
  results.steps.push({ step: 4, name: 'Check Message Status', ...step4 });
  
  // Step 5: Check History
  const step5 = messageStep5_CheckContainerHistory();
  results.steps.push({ step: 5, name: 'Check Message History', ...step5 });
  
  // Summary
  console.log('\n📊 MESSAGE AGENT DIAGNOSTIC SUMMARY:');
  results.steps.forEach(step => {
    console.log(`${step.success ? '✅' : '❌'} Step ${step.step}: ${step.name}`);
  });
  
  const passed = results.steps.filter(s => s.success).length;
  console.log(`\n${passed}/5 message agent steps passed`);
  
  return results;
}