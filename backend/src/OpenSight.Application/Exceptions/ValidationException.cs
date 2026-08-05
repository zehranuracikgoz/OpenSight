namespace OpenSight.Application.Exceptions;

/// istemciden gelen geçersiz veriyi belirtiyor - controller bunu yakalayıp 400 dönüyor
public class ValidationException : Exception
{
    public ValidationException(string message) : base(message)
    {
    }
}
