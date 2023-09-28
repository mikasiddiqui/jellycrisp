$(document).ready(function () {
    var counter = 0;

    $("#addrow").on("click", function () {
        var newRow = $("<tr>");
        var cols = "";

        cols += '<td><input type="text" class="form-control" name="inputName' + counter + '"/></td>';
        cols += '<td><select class="form-control" id="selectModel' + counter + '"><option selected>Choose...</option><option>...</option></select></td>';
        cols += '<td><select id="selectInput' + counter + '" class="form-control"><option selected>String</option><option>Integer</option><option>Image</option><option>Float</option><option>Boolean</option><option>List</option><option>Array</option><option>Tensor</option></select></td>';

        cols += '<td><select class="form-control" id="selectSource' + counter + '"><option selected>Choose...</option><option>User</option><option>Model</option></select></td>';

        cols += '<td><input type="button" class="ibtnDel btn btn-md btn-danger custom-btn"  value="Delete"></td>';
        newRow.append(cols);
        $("table.order-list").append(newRow);
        counter++;
    });



    $("table.order-list").on("click", ".ibtnDel", function (event) {
        $(this).closest("tr").remove();       
        counter -= 1
    });


});



function calculateRow(row) {
    var price = +row.find('input[name^="price"]').val();

}

function calculateGrandTotal() {
    var grandTotal = 0;
    $("table.order-list").find('input[name^="price"]').each(function () {
        grandTotal += +$(this).val();
    });
    $("#grandtotal").text(grandTotal.toFixed(2));
}