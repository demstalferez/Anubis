import base64
import json
import traceback
import urllib.parse
from typing import Union, Tuple, Any

from flask import request

from anubis.utils.auth import LackCourseContext, current_user, AuthenticationError
from anubis.utils.services.logger import logger
from anubis.models import (
    Course,
    TAForCourse,
    ProfessorForCourse,
    Assignment,
    AssignmentRepo,
    AssignedStudentQuestion,
    AssignmentQuestion,
    AssignmentTest,
    Submission,
    TheiaSession,
    StaticFile,
    User,
    InCourse,
)


def get_course_context(full_stop: bool = True) -> Union[None, Course]:
    """
    Get the course context for the current admin user. On the anubis website
    when a user is an admin, they have a context autocomplete at the top
    with all the courses they are admins for. When they select a course,
    it sets a course context cookie.

    This function pulls that information out of the cookie, verifies
    that the user is truly an admin for that course, then returns the
    corresponding Course object.

    The full_stop option is there to save time. When it is set,
    any discrepancy found (like say if the current user is not
    an admin for the course they have set) then a LackCourseContext
    exception will be raised. When this happens, there is a high
    level wrapper that handles returns a 400 to the user saying
    they lack the proper course context / privileges.

    :param full_stop:
    :return:
    """

    def _get_course_context():
        """
        Putting this in a separate function made handling the
        full_stop option slightly easier.

        :return:
        """

        # Get the raw course cookie string
        course_raw = request.cookies.get('course', default=None)

        # If there is no cookie set, then return None
        if course_raw is None:
            return None

        # Attempt to urllib unquote, base64 decode, then json loads
        # the raw cookie. There is a lot that can go wrong here, so
        # just handle any exceptions.
        try:
            course_data = json.loads(base64.urlsafe_b64decode(
                urllib.parse.unquote(course_raw).encode()
            ))
        except Exception as e:
            # Print the exception traceback
            logger.error(traceback.format_exc())
            logger.error(str(e))
            return None

        # Get the course id from the loaded course data
        course_id = course_data.get('id', None)

        # If there was no id in the course data, then return None
        if course_id is None:
            return None

        # Verify that the current user is actually an admin for
        # this course.
        if not is_course_admin(course_id):
            raise AuthenticationError()

        # Get the course object
        course = Course.query.filter(
            Course.id == course_id,
        ).first()

        # And return it
        return course

    # Get the current course context
    context = _get_course_context()

    # If full_stop is on, then verify we got a valid context,
    # or raise a LackCourseContext.
    if context is None and full_stop:
        raise LackCourseContext()

    # Return the course context
    return context


def is_course_superuser(course_id: str) -> bool:
    """
    Use this function to verify if the current user is a superuser for
    the specified course_id. A user is a superuser for a course if they are
    a professor, or if they are a superuser.

    :param course_id:
    :return:
    """
    # Get the current user
    user = current_user()

    # If they are a superuser, then we can just return True
    if user.is_superuser:
        return True

    # Check to see if they are a professor for the current course
    prof = ProfessorForCourse.query.filter(
        ProfessorForCourse.owner_id == user.id,
        TAForCourse.course_id == course_id,
    ).first()

    # Return True if they are a professor for the course
    return prof is not None


def is_course_admin(course_id: str) -> bool:
    """
    Use this function to verify if the current user is an admin for
    the specified course_id. A user is an admin for a course if they are
    a ta, professor, or if they are a superuser.

    :param course_id:
    :return:
    """
    # Get the current user
    user = current_user()

    # If they are a superuser, then just return True
    if user.is_superuser:
        return True

    # Check to see if they are a TA for the course
    ta = TAForCourse.query.filter(
        TAForCourse.owner_id == user.id,
        TAForCourse.course_id == course_id,
    ).first()

    # Check to see if they are a professor for the course
    prof = ProfessorForCourse.query.filter(
        ProfessorForCourse.owner_id == user.id,
        TAForCourse.course_id == course_id,
    ).first()

    # Return True if they are either a ta or professor
    return ta is not None or prof is not None


def assert_course_admin(course_id: str = None):
    """
    Use this function to assert that the current user is
    an admin for the specified course. If they are not, then
    an authentication error will be raised.

    The AuthenticationError will be handled in a high level
    flask view wrapper that will return whatever string we
    put as the message for the authentication error.

    :param course_id:
    :return:
    """
    if not is_course_admin(course_id):
        raise LackCourseContext('Requires course TA permissions')


def assert_course_superuser(course_id: str = None):
    """
    Use this function to assert that the current user is
    a superuser for the specified course. If they are not, then
    an authentication error will be raised.

    The AuthenticationError will be handled in a high level
    flask view wrapper that will return whatever string we
    put as the message for the authentication error.

    :param course_id:
    :return:
    """
    if not is_course_superuser(course_id):
        raise LackCourseContext('Requires course Professor permissions')


def assert_course_context(*models: Tuple[Any]):
    """
    This function checks that all the sqlalchemy objects that are
    passed to this function are within the current course context.
    If they are not, then a LackCourseContext will be raised.

    :param models:
    :return:
    """

    # Get the current course context
    context = get_course_context()

    # Create a stack of objects to check
    object_stack = list(models)

    # This next bit of code definitely deserves an explanation. Most
    # all the sqlalchemy models have some relationship or backref
    # that leads to a course object. What I am doing here is using a
    # stack to continuously access the next backref or relationship
    # until we get to a course object.
    #
    # Since the majority of models have either an .assignment or
    # .course backref, we can simplify things a bit by iterating
    # over all the model types that have the same name for the next
    # relationship or backref to access.

    # Iterate until the stack is empty
    while len(object_stack) != 0:
        model = object_stack.pop()

        # If the model is a course, then we can actually do the context check
        if isinstance(model, Course):

            # Check that the current user is an admin for the course object
            if not is_course_admin(model.id):
                raise LackCourseContext('You cannot edit resources in this course context')

            # Verify that the course object is the same as the set context
            if model.id != context.id:
                raise LackCourseContext('Cannot view or edit resource outside course context')

        # Group together all the models that have an
        # assignment backref or relationship
        for model_type in [
            Submission,
            AssignmentTest,
            AssignmentRepo,
            AssignedStudentQuestion,
            AssignmentQuestion,
        ]:
            if isinstance(model, model_type):
                object_stack.append(model.assignment)
                continue

        # Group together all the models that have a course
        # backref or relationship
        for model_type in [
            Assignment,
            StaticFile,
            TheiaSession,
        ]:
            if isinstance(model, model_type):
                object_stack.append(model.course)
                continue

        # ---------------------------------
        # If the model is a user then we need to handle it a
        # little differently. We'll just need to verify that
        # the student is in the course.
        if isinstance(model, User):

            # Get course student is in
            in_course = InCourse.query.filter(
                InCourse.owner_id == model.id,
                InCourse.course_id == context.id,
            ).first()

            # Verify that they are in the course
            if in_course is None:
                raise LackCourseContext('Student is not within this course context')