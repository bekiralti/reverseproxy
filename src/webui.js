// Globale Variablen
const es = new EventSource("/events");  // This basically initiates the SSE
let current_ids = Set();

// The function assigned to onmessage gets called by the Client's Browser whenever an SSE arrives
es.onmessage = (e) => {
    const data = JSON.parse(e.data);                     // Making an array out the e.data string
    const ids = new Set(data.map(d => d.connection_id))  // We are extracting the id numbers and saving them as a Set

    // Hinzufügen
    for id in ids:
        if !current_ids.has(id):
            // Hinzufügen

    // Entfernen
    for id in ids
        // Ehm...
};