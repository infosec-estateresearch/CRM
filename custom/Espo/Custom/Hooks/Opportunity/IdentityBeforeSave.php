<?php

namespace Espo\Custom\Hooks\Opportunity;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * CRM-IDINT-001R: identity integrity for Opportunity (BeforeSave). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 */
class IdentityBeforeSave implements BeforeSave
{
    /** Hook order (runs after the platform's own save hooks, so it sees the final values); the platform's default is 9. */
    public static int $order = 99;

    public function __construct(private IdentityGuard $guard)
    {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $this->guard->beforeSave($entity, $options);
    }
}
