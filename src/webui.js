const es = new EventSource("/events");  // This basically initiates the SSE

// The function assigned to onmessage gets called by the Client's Browser whenever an SSE arrives
es.onmessage = (event) => {
    console.log(event.data)
};

console.log("ENDE");