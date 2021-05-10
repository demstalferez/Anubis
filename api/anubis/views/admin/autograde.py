from flask import Blueprint

from anubis.models import Submission, Assignment, User, InCourse
from anubis.utils.auth import require_admin
from anubis.utils.http.decorators import json_response
from anubis.utils.http.https import success_response, error_response, get_number_arg
from anubis.utils.lms.autograde import bulk_autograde, autograde, autograde_submission_result_wrapper
from anubis.utils.lms.course import assert_course_admin, assert_course_context, get_course_context
from anubis.utils.lms.questions import get_assigned_questions
from anubis.utils.services.elastic import log_endpoint
from anubis.utils.services.cache import cache

autograde_ = Blueprint("admin-autograde", __name__, url_prefix="/admin/autograde")


@autograde_.route("/assignment/<assignment_id>")
@require_admin()
@cache.memoize(timeout=60)
@json_response
def admin_autograde_assignment_assignment_id(assignment_id):
    """
    Calculate result statistics for an assignment. This endpoint is
    potentially very IO and computationally expensive. We basically
    need to load the entire submission history out of the database
    for the given assignment, then do calculations per user. For
    this reason, much of the individual computations here are quite
    heavily cached.

    * Due to how heavily cached the stats calculations are, once cached
    they will not be updated until there is a cache bust after the
    timeout. *

    :param assignment_id:
    :return:
    """

    # Get options for autograde calculations
    limit = get_number_arg("limit", 10)
    offset = get_number_arg("offset", 0)

    # Pull the assignment object
    assignment = Assignment.query.filter(
        Assignment.id == assignment_id
    ).first()

    # Verify that we got an assignment
    if assignment is None:
        return error_response('assignment does not exist')

    # Verify that the current course context, and the assignment course match
    assert_course_context(assignment)

    # Get the (possibly cached) autograde calculations
    bests = bulk_autograde(assignment_id, limit=limit, offset=offset)

    # Pass back the results
    return success_response({"stats": bests})


@autograde_.route("/for/<assignment_id>/<user_id>")
@require_admin()
@cache.memoize(timeout=60)
@json_response
def admin_autograde_for_assignment_id_user_id(assignment_id, user_id):
    """
    Get the autograde results for a specific assignment and user.

    :param assignment_id:
    :param user_id:
    :return:
    """

    # Pull the assignment object
    assignment = Assignment.query.filter(
        Assignment.id == assignment_id
    ).first()

    # Verify that we got an assignment
    if assignment is None:
        return error_response('assignment does not exist')

    # Pull the student user object
    student = User.query.filter(User.id == user_id).first()

    # Verify that the current course context, and the assignment course match
    assert_course_context(assignment, student)

    # Calculate the best submission for this student and assignment
    submission_id = autograde(user_id, assignment_id)

    # Pass back the
    return success_response({
        "stats": autograde_submission_result_wrapper(
            assignment, student.id, student.netid,
            student.name, submission_id
        )
    })


@autograde_.route("/submission/<string:assignment_id>/<string:netid>")
@require_admin()
@log_endpoint("cli", lambda: "submission-stats")
@cache.memoize(timeout=60)
@json_response
def private_submission_stats_id(assignment_id: str, netid: str):
    """
    Get absolutely everything we have for specific submission.

    * This is can be a lot of data *

    :param assignment_id:
    :param netid:
    :return:
    """

    # Get the user matching the specified netid
    student = User.query.filter(User.netid == netid).first()

    # Make sure the user exists
    if student is None:
        return error_response('User does not exist')

    # Pull the assignment object
    assignment = Assignment.query.filter(Assignment.id == assignment_id).first()

    # Verify that we got an assignment
    if assignment is None:
        return error_response('assignment does not exist')

    # Verify that the current course context, and the assignment course match
    assert_course_context(assignment, student)

    # Calculate the best submission
    submission_id = autograde(student.id, assignment.id)

    # Set the default for the full_data of the submission
    submission_full_data = None

    # Get the submission full_data if there was a best submission
    if submission_id is not None:
        # Pull the submission
        submission = Submission.query.filter(
            Submission.id == submission_id
        ).first()

        # Get the full picture of the submission
        submission_full_data = submission.admin_data

    # Pass back the full, unobstructed view of the student,
    # assignment, question assignments, and submission data
    return success_response({
        "student": student.data,
        "course": assignment.course.data,
        "assignment": assignment.full_data,
        "submission": submission_full_data,
        "questions": get_assigned_questions(
            assignment.id, student.id, True
        ),
    })