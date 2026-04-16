// HR Dashboard JavaScript Functions

function updateAllocation(userId) {
    var vacation = document.getElementById('vacation-' + userId).value;
    var personal = document.getElementById('personal-' + userId).value;
    var sick = document.getElementById('sick-' + userId).value;
    var volunteer = document.getElementById('volunteer-' + userId).value;
    var jury = document.getElementById('jury-' + userId).value;
    
    fetch('/update_user_allocations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: userId,
            vacation: vacation,
            personal: personal,
            sick: sick,
            volunteer: volunteer,
            jury_duty: jury
        })
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        if (data.success) {
            alert('Allocations updated successfully!');
            location.reload();
        } else {
            alert('Error updating allocations: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(error) {
        alert('Error: ' + error);
    });
}